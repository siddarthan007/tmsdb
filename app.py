from datetime import datetime
import mysql.connector
from dotenv import dotenv_values
from mysql.connector import Error
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from random import randint
import logging
import os
from functools import wraps
import qrcode
import io
import base64


logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

app.secret_key = os.urandom(24)

config = dotenv_values(".env")

DB_HOST = 'localhost'
DB_DATABASE = config.get('DB_DATABASE', 'your_default_db_name')
DB_USER = config.get('DB_USER', 'your_default_user')
DB_PASSWORD = config.get('DB_PASSWORD', 'your_default_password')

GOLD_SEAT_THRESHOLD = 1000
SEATS_PER_ROW = 10

def format_time_tuple(time_int):
    if time_int is None:
        return (None, None)
    try:
        hour = time_int // 100
        minute = time_int % 100
        minute_str = f"{minute:02d}"
        return (hour, minute_str)
    except (TypeError, ValueError):
        logging.warning(f"Could not format time from input: {time_int}")
        return (None, None)
    
def generate_id():
    return randint(1_000_000, 9_999_999)

def runQuery(query, params=None, fetch_one=False, last_row_id=False):
    results = None
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            database=DB_DATABASE,
            user=DB_USER,
            password=DB_PASSWORD
        )
        if connection.is_connected():
            cursor = connection.cursor(buffered=True)
            logging.info(f"Executing query: {cursor.statement}")
            cursor.execute(query, params or ())
            if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CALL')):
                connection.commit()
                logging.info("Query committed.")
            if cursor.description:
                if fetch_one:
                    results = cursor.fetchone()
                elif last_row_id:
                    results = cursor.lastrowid
                else:
                    results = cursor.fetchall()
                logging.info(f"Query yielded results: {'Yes' if results else 'No'}")
            else:
                results = []
                logging.info("Query did not yield results (e.g., successful DML/DDL).")
            return results
    except Error as e:
        logging.error(f"MySQL Error executing query '{query[:100]}...': {e}")
        return None
    except Exception as e:
        logging.error(f"General Error during query execution: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            logging.info("MySQL connection closed.")

def render_bulma_notification(message, level='is-danger', size=''):
    return f'<div class="notification {level} {size} p-3 my-4 mx-4"> {message} </div>'

def login_required(role="any"):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session:
                logging.warning("Unauthorized access attempt to {request.path} detected.")
                return redirect(url_for('renderLoginOrIndex'))
            if role != "any" and session.get('user_role') != role:
                return "Access Denied: You do not have permission to access this page.", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def renderLoginOrIndex():
    if 'user_role' in session:
        user_role = session['user_role']
        if user_role == 'cashier':
            logging.info(f"Session found for role '{user_role}'. Rendering cashier dashboard.")
            return render_template('cashier.html')
        elif user_role == 'manager':
            logging.info(f"Session found for role '{user_role}'. Rendering manager dashboard.")
            return render_template('manager.html')
        else:
            logging.warning(f"Session found with unknown role: '{user_role}'. Clearing session.")
            session.clear()
            return render_template('login.html', message="Invalid session role. Please log in again.")
    else:
        logging.info("No active session found. Rendering login page.")
        return render_template('login.html')

@app.route('/login', methods=['POST'])
def verifyAndRenderRespective():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        return render_template('loginFail.html', message="Username or password cannot be empty.")
    
    query = "SELECT user_id, username, password_hash, role FROM users WHERE username = %s"
    user_data = runQuery(query, (username,), fetch_one=True)

    if user_data:
        user_id, db_username, db_password_hash, user_role = user_data
        if check_password_hash(db_password_hash, password):
            session.clear()
            session['user_id'] = user_id
            session['username'] = db_username
            session['user_role'] = user_role
            logging.info(f"User {db_username} logged in as {user_role}.")

            return redirect(url_for('renderLoginOrIndex'))
        else:
            logging.warning(f"Failed login attempt for user {username}: Incorrect password.")
            return render_template('loginFail.html', message="Incorrect username or password.")
    else:
        logging.warning(f"Failed login attempt for user {username}: User not found.")
        return render_template('loginFail.html', message="User not found.")
    
@app.route('/logout')
@login_required(role="any")
def logout():
    session.pop('user_id', None)
    session.pop('user_role', None)
    session.pop('username', None)
    return redirect(url_for('renderLoginOrIndex'))

@app.route('/getMoviesShowingOnDate', methods=['POST'])
@login_required(role="cashier")
def moviesOnDate():
    show_date = request.form.get('date')
    if not show_date:
        return render_bulma_notification('Invalid date provided.', 'is-warning')
    query = """
        SELECT DISTINCT m.movie_id, m.movie_name, s.type
        FROM movies m
        JOIN shows s ON m.movie_id = s.movie_id
        WHERE s.Date = %s
    """
    results = runQuery(query, (show_date,))
    if results is None:
        return render_bulma_notification('Error retrieving movie data. Please try again later.', 'is-danger')
    if not results:
        return render_bulma_notification('No Movies Showing on this Date', 'is-info')
    else:
        return render_template('movies.html', movies=results)

@app.route('/getTimings', methods=['POST'])
@login_required(role="cashier")
def timingsForMovie():
    show_date = request.form.get('date')
    movie_id = request.form.get('movieID')
    movie_type = request.form.get('type')
    if not all([show_date, movie_id, movie_type]):
        return render_bulma_notification('Missing required information (date, movieID, or type).', 'is-warning')
    query = """
        SELECT time FROM shows
        WHERE Date = %s AND movie_id = %s AND type = %s
        ORDER BY time
    """
    try:
        results = runQuery(query, (show_date, int(movie_id), movie_type))
    except ValueError:
        return render_bulma_notification('Invalid Movie ID format.', 'is-danger')
    if results is None:
        return render_bulma_notification('Error retrieving timings. Please try again later.', 'is-danger')
    timings_list = []
    for row in results:
        time_int = row[0]
        hour, minute_str = format_time_tuple(time_int)
        if hour is not None:
            timings_list.append((time_int, hour, minute_str))
    return render_template('timings.html', timings=timings_list)

@app.route('/getShowID', methods=['POST'])
@login_required(role="cashier")
def getShowID():
    show_date = request.form.get('date')
    movie_id = request.form.get('movieID')
    movie_type = request.form.get('type')
    time_str = request.form.get('time')
    if not all([show_date, movie_id, movie_type, time_str]):
        return jsonify({"error": "Missing required information."}), 400
    query = """
        SELECT show_id FROM shows
        WHERE Date = %s AND movie_id = %s AND type = %s AND time = %s
    """
    try:
        params = (show_date, int(movie_id), movie_type, int(time_str))
        result = runQuery(query, params, fetch_one=True)
    except ValueError:
        return jsonify({"error": "Invalid numeric input for movie ID or time."}), 400
    if result:
        return jsonify({"showID": result[0]})
    elif result is None:
        return jsonify({"error": "Database error occurred."}), 500
    else:
        return jsonify({"error": "Show not found for the given details."}), 404

@app.route('/getAvailableSeats', methods=['POST'])
@login_required(role="cashier")
def getSeating():
    show_id_str = request.form.get('showID')
    if not show_id_str:
        return render_bulma_notification('Missing Show ID.', 'is-warning')

    query_hall_info = """
        SELECT h.class, h.no_of_seats
        FROM shows s
        JOIN halls h ON s.hall_id = h.hall_id
        WHERE s.show_id = %s
    """
    query_booked = """
        SELECT seat_no FROM booked_tickets
        WHERE show_id = %s
    """
    try:
        show_id = int(show_id_str)
        hall_results = runQuery(query_hall_info, (show_id,))
        booked_results = runQuery(query_booked, (show_id,))
    except ValueError:
        return render_bulma_notification('Invalid Show ID format.', 'is-danger')

    if hall_results is None or booked_results is None:
        return render_bulma_notification('Error retrieving seating information.', 'is-danger')
    if not hall_results:
        return render_bulma_notification('Hall information not found for this show.', 'is-info')

    total_gold = 0
    total_standard = 0
    for row in hall_results:
        seat_class, num_seats = row
        if seat_class and seat_class.lower() == 'gold':
            total_gold = num_seats if num_seats else 0
        elif seat_class and seat_class.lower() == 'standard':
            total_standard = num_seats if num_seats else 0

    booked_seat_nos = {row[0] for row in booked_results}

    def generate_seat_layout(total_seats, start_db_no, seat_class):
        rows_data = []
        if total_seats <= 0:
            return rows_data
        num_rows = (total_seats + SEATS_PER_ROW - 1) // SEATS_PER_ROW
        seat_counter = 0
        for r in range(num_rows):
            row_letter = chr(ord('A') + r)
            row_seats = []
            for s in range(SEATS_PER_ROW):
                seat_counter += 1
                if seat_counter > total_seats:
                    break
                display_code = f"{row_letter}{s + 1}"
                db_no = start_db_no + seat_counter -1
                status = 'booked' if db_no in booked_seat_nos else 'available'
                row_seats.append({
                    "code": display_code,
                    "db_no": db_no,
                    "status": status,
                    "class": seat_class
                })
            rows_data.append({"letter": row_letter, "seats": row_seats})
        return rows_data

    gold_layout = generate_seat_layout(total_gold, 1 + GOLD_SEAT_THRESHOLD, 'gold')
    standard_layout = generate_seat_layout(total_standard, 1, 'standard')

    return render_template('seating.html', goldLayout=gold_layout, standardLayout=standard_layout)

@app.route('/getPrice', methods=['POST'])
@login_required(role="cashier")
def getPriceForClass():
    show_id_str = request.form.get('showID')
    seat_class = request.form.get('seatClass')
    if not all([show_id_str, seat_class]):
        return render_bulma_notification('Missing Show ID or Seat Class.', 'is-warning')
    query = """
        SELECT pl.price
        FROM shows s
        LEFT JOIN price_listing pl ON s.price_id = pl.price_id
        WHERE s.show_id = %s
    """
    try:
        show_id = int(show_id_str)
        result = runQuery(query, (show_id,), fetch_one=True)
    except ValueError:
        return render_bulma_notification('Invalid Show ID format.', 'is-danger')
    if result is None:
        return render_bulma_notification('Error retrieving price information.', 'is-danger')
    if not result or result[0] is None:
        return render_bulma_notification('Prices have not been assigned to this show yet. Please check later.', 'is-info')
    try:
        base_price = int(result[0])
        price = base_price
        if seat_class.lower() == 'gold':
            price = int(base_price * 1.5)
        return f'''
            <div class="content has-text-centered mb-3">
                <p class="is-size-5 has-text-weight-semibold">Ticket Price: ₹ {price}</p>
                <p class="is-size-6 has-text-weight-semibold">Class: {seat_class.capitalize()}</p>
            </div>
            <div class="field">
                <div class="control has-text-centered">
                    <button class="button is-success" onclick="confirmBooking()">Confirm Booking</button>
                </div>
            </div>
        '''
    except (ValueError, TypeError) as e:
        logging.error(f"Error calculating price for show {show_id_str}: {e}")
        return render_bulma_notification('Error processing price information.', 'is-danger')

@app.route('/insertBooking', methods=['POST'])
@login_required(role="cashier")
def createBooking():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request format. JSON expected."}), 400

    show_id_str = data.get('showID')
    selected_seats = data.get('selectedSeats')
    customer_name = data.get('customerName', '').strip()
    customer_phone = data.get('customerPhone', '').strip()

    if not all([show_id_str, selected_seats, customer_name, customer_phone]):
        return render_bulma_notification('Missing booking information (Show ID or Selected Seats).', 'is-warning')
    
    customer_id = None
    
    try:
        customer_query = "SELECT customer_id FROM customers WHERE customer_phone = %s"
        customer_result = runQuery(customer_query, (customer_phone,), fetch_one=True)

        if customer_result:
            customer_id = customer_result[0]
            update_customer_query = "UPDATE customers SET customer_name = %s WHERE customer_id = %s AND customer_name != %s"
            runQuery(update_customer_query, (customer_name, customer_id, customer_name))
            logging.info(f"Found existing customer ID: {customer_id} for phone {customer_phone}")
        else:
            insert_customer_query = "INSERT INTO customers (customer_name, customer_phone) VALUES (%s, %s)"
            runQuery(insert_customer_query, (customer_name, customer_phone))
            customer_id_query = "SELECT customer_id FROM customers WHERE customer_phone = %s"
            customer_id_result = runQuery(customer_id_query, (customer_phone,), fetch_one=True)
            if customer_id_query:
                customer_id = customer_id_result[0]
                logging.info(f"Created new customer ID: {customer_id} for {customer_name}, {customer_phone}")
            else:
                return render_bulma_notification(f'Failed to retrieve customer ID after inserting customer with phone {customer_phone}.', 'is-warning')

        booking_ref = str(generate_id())

        attempts = 0
        max_attempts = 5
        while attempts < max_attempts:
            check_booking_query = "SELECT booking_ref FROM bookings WHERE booking_ref = %s"
            result = runQuery(check_booking_query, (booking_ref,), fetch_one=True)
            if not result:
                break
            logging.warning(f"Booking reference collision for {booking_ref}, retrying...")
            attempts += 1
        else:
            return render_bulma_notification('Failed ro generate unique booking reference.', 'is-error')
        
        insert_booking_query = "INSERT INTO bookings (booking_ref, customer_id) VALUES (%s, %s)"
        runQuery(insert_booking_query, (booking_ref, customer_id))
        logging.info(f"Created booking record with ref: {booking_ref} for customer ID: {customer_id}")

        booked_ticket_details = []
        show_id = int(show_id_str)

        query = """
            INSERT INTO booked_tickets
            (ticket_no, show_id, seat_no, booking_ref)
            VALUES (%s, %s, %s, %s)
        """

        for seat in selected_seats:
            seat_db_no = seat.get('db_no')
            seat_code = seat.get('code')
            seat_class = seat.get('class', '').lower()

            ticket_no = None
            attempts = 0
            max_attempts = 5
            while attempts < max_attempts:
                ticket_no = generate_id()
                check_query = "SELECT ticket_no FROM booked_tickets WHERE ticket_no = %s"
                existing = runQuery(check_query, (ticket_no,), fetch_one=True)
                if not existing:
                    break
                logging.warning(f"Ticket number collision for {ticket_no}, retrying...")
                attempts += 1
            else:
                logging.error("Failed to generate a unique ticket number after multiple attempts.")
                return render_bulma_notification('Error generating ticket number. Please try booking again.', 'is-danger')
            
            params = (
                    ticket_no,
                    show_id,
                    seat_db_no,
                    booking_ref
            )
            logging.info(f"Attempting to insert ticket: {params}")
            result = runQuery(query, params)

            if isinstance(result, list) and not result:
                booked_ticket_details.append({
                    "ticket_no": ticket_no,
                    "seat_display": f"{seat_code} ({seat_class.capitalize()})"
                })
            else:
                logging.error(f"Booking insertion potentially failed for show {show_id}, seat {seat_db_no}. runQuery returned: {result}")
                return render_bulma_notification('Booking Failed. The seat might have just been taken, or a database error occurred.', 'is-danger')
        
        seats_booked_str = ", ".join([t["seat_display"] for t in booked_ticket_details])
        ticket_url = url_for('show_ticket', booking_ref=booking_ref, _external=True)

        success_html = f'''
            <div class="notification is-success is-light has-text-centered">
                <p class="is-size-5 has-text-weight-semibold mb-1">Booking Confirmed!</p>
                <p class="is-size-6">Booking Reference: <strong>{booking_ref}</strong></p>
                <p class="is-size-7">Seats Booked: {seats_booked_str}</p>
                {'<p class="is-size-7">Name: ' + customer_name + '</p>' if customer_name else ''}
                {'<p class="is-size-7">Phone: ' + customer_phone + '</p>' if customer_phone else ''}
                <a href="{ticket_url}" class="button is-small is-link mt-2" target="_blank">View/Print Ticket(s)</a>
            </div>
        '''

        return success_html
    except ValueError:
        return render_bulma_notification('Invalid numeric input for Show ID or Seat Number.', 'is-danger')
    except Exception as e:
        logging.error(f"Error during booking insertion: {e}")
        return render_bulma_notification('An unexpected error occurred during booking.', 'is-danger')

    
@app.route('/getTotalPrice', methods=['POST'])
@login_required(role="cashier")
def get_total_price():
    data = request.get_json()
    show_id_str = data.get('showID')
    selected_seats = data.get('seats', [])

    if not show_id_str or not selected_seats:
        return jsonify({"error": "Missing Show ID or selected seats."}), 400

    query = """
        SELECT pl.price
        FROM shows s
        JOIN price_listing pl ON s.price_id = pl.price_id
        WHERE s.show_id = %s
    """
    try:
        show_id = int(show_id_str)
        result = runQuery(query, (show_id,), fetch_one=True)
    except ValueError:
         return jsonify({"error": "Invalid Show ID."}), 400

    if result is None or not result or result[0] is None:
        return jsonify({"error": "Price not found for this show."}), 404

    base_price = int(result[0])
    total_price = 0
    seat_details_html = ""

    print(selected_seats)

    for seat in selected_seats:
        seat_class = seat.get('seatClass', '').lower()
        seat_code = seat.get('seatCode')
        price = base_price
        if seat_class == 'gold':
            price = int(base_price * 1.5)
        total_price += price
        seat_details_html += f'<span class="tag is-info mr-1 mb-1">Seat {seat_code} ({seat_class.capitalize()}) - ₹{price}</span> '

    return f'''
        <div class="box has-background-darker p-4">
    <h5 class="title is-4 has-text-warning has-text-centered">Booking Summary</h5>
    <hr class="has-background-grey-dark">

    <div class="mb-4 has-text-centered" id="selected-seats-display">
        <p class="is-size-6 has-text-weight-semibold mb-2">Selected Seats:</p>
        <div class="tags is-centered">
             {seat_details_html if seat_details_html else '<span class="tag is-light">No seats selected</span>'}
        </div>
    </div>

    <div class="has-text-centered mb-4">
         <p class="is-size-5 has-text-weight-bold">Total Price: <span class="has-text-success">₹ {total_price} </span></p>
         <p class="is-size-6"> (excluding GSTs)</p>
    </div>

    <hr class="has-background-grey-dark">

    <div class="columns is-mobile is-centered">
        <div class="column is-narrow" style="min-width: 250px;">
            <div class="field">
                <label class="label has-text-light" for="customerNameInput">Customer Name</label>
                <div class="control has-icons-left">
                    <input class="input" type="text" id="customerNameInput" placeholder="Enter name">
                    <span class="icon is-left">
                        <i class="fas fa-user"></i>
                    </span>
                </div>
            </div>

            <div class="field">
                <label class="label has-text-light" for="customerPhoneInput">Phone Number</label>
                <div class="control has-icons-left">
                    <input class="input" type="tel" id="customerPhoneInput" placeholder="Enter phone">
                     <span class="icon is-left">
                        <i class="fas fa-phone"></i>
                    </span>
                </div>
            </div>
        </div>
    </div>

    <div class="field mt-5">
        <div class="control has-text-centered">
            <button id="confirm-booking-button" class="button is-success is-medium" onclick="confirmBooking()" {'disabled' if not selected_seats else ''}>
                 <span class="icon is-small">
                    <i class="fas fa-check"></i>
                 </span>
                 <span>Confirm Booking</span>
            </button>
        </div>
    </div>
</div>
    '''

@app.route('/getShowsShowingOnDate', methods=['POST'])
@login_required(role="manager")
def getShowsOnDate():
    show_date = request.form.get('date')
    if not show_date:
        return render_bulma_notification('Invalid date provided.', 'is-warning')
    query = """
        SELECT s.show_id, m.movie_name, s.type, s.time
        FROM shows s
        JOIN movies m ON s.movie_id = m.movie_id
        WHERE s.Date = %s
        ORDER BY s.time, m.movie_name
    """
    results = runQuery(query, (show_date,))
    if results is None:
        return render_bulma_notification('Error retrieving show data. Please try again later.', 'is-danger')
    if not results:
        return render_bulma_notification('No Shows Scheduled for this Date', 'is-info')
    shows_formatted = []
    for row in results:
        show_id, movie_name, show_type, time_int = row
        hour, minute_str = format_time_tuple(time_int)
        if hour is not None:
            shows_formatted.append([show_id, movie_name, show_type, hour, minute_str])
    return render_template('shows.html', shows=shows_formatted)

@app.route('/getBookedWithShowID', methods=['POST'])
@login_required(role="manager")
def getBookedTickets():
    show_id_str = request.form.get('showID')
    if not show_id_str:
        return render_bulma_notification('Missing Show ID.', 'is-warning')
    query = """
        SELECT ticket_no, seat_no
        FROM booked_tickets
        WHERE show_id = %s
        ORDER BY seat_no
    """
    try:
        show_id = int(show_id_str)
        results = runQuery(query, (show_id,))
    except ValueError:
        return render_bulma_notification('Invalid Show ID format.', 'is-danger')
    if results is None:
        return render_bulma_notification('Error retrieving booking data.', 'is-danger')
    if not results:
        return render_bulma_notification('No Bookings Found for this Show', 'is-info')
    tickets_formatted = []
    for row in results:
        ticket_no, seat_db_no = row
        if seat_db_no > GOLD_SEAT_THRESHOLD:
            seat_display_no = seat_db_no - GOLD_SEAT_THRESHOLD
            seat_class = 'Gold'
        else:
            seat_display_no = seat_db_no
            seat_class = 'Standard'
        tickets_formatted.append([ticket_no, seat_display_no, seat_class])
    return render_template('bookedTickets.html', tickets=tickets_formatted)

@app.route('/fetchMovieInsertForm', methods=['GET'])
@login_required(role="manager")
def getMovieForm():
    return render_template('movieForm.html')

@app.route('/insertMovie', methods=['POST'])
@login_required(role="manager")
def insertMovie():
    movie_name = request.form.get('movieName')
    movie_len_str = request.form.get('movieLen')
    movie_lang = request.form.get('movieLang')
    types_str = request.form.get('types')
    start_showing = request.form.get('startShowing')
    end_showing = request.form.get('endShowing')
    if not all([movie_name, movie_len_str, movie_lang, types_str, start_showing, end_showing]):
        return render_bulma_notification('Missing required movie information.', 'is-warning')
    
    start_showing = datetime.strptime(start_showing, "%d %B, %Y").date()
    end_showing = datetime.strptime(end_showing, "%d %B, %Y").date()
    
    try:
        movie_len = int(movie_len_str)
        if movie_len <= 0: raise ValueError("Movie length must be positive.")
    except ValueError as e:
        return render_bulma_notification(f'Invalid movie length: {e}', 'is-danger')
    movie_id = None
    attempts = 0
    max_attempts = 10
    while attempts < max_attempts:
        movie_id = generate_id()
        check_id_query = "SELECT movie_id FROM movies WHERE movie_id = %s"
        id_exists = runQuery(check_id_query, (movie_id,), fetch_one=True)
        if not id_exists: break
        attempts += 1
    else:
        logging.error("Failed to generate a unique movie ID.")
        return render_bulma_notification('Error generating unique movie ID. Please try again.', 'is-danger')
    insert_movie_query = """
        INSERT INTO movies (movie_id, movie_name, length, language, show_start, show_end)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    movie_params = (movie_id, movie_name, movie_len, movie_lang, start_showing, end_showing)
    print(movie_params)
    movie_insert_result = runQuery(insert_movie_query, movie_params)
    if not isinstance(movie_insert_result, list):
        logging.error(f"Movie insertion failed for {movie_name}. runQuery returned: {movie_insert_result}")
        return render_bulma_notification('Failed to add movie details. Database error occurred.', 'is-danger')
    sub_types = [t.strip() for t in types_str.split(' ') if t.strip()]
    type_params_tuple = tuple(sub_types[:3] + [None]*(3-len(sub_types)))
    insert_types_query = """
        INSERT INTO types (movie_id, type1, type2, type3) VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE type1=VALUES(type1), type2=VALUES(type2), type3=VALUES(type3)
    """
    types_params = (movie_id,) + type_params_tuple
    types_insert_result = runQuery(insert_types_query, types_params)
    if isinstance(types_insert_result, list):
        return f'''
            <div class="notification is-success is-light has-text-centered">
                <p class="is-size-5 has-text-weight-semibold mb-1">Movie Successfully Added!</p>
                <p class="is-size-6">Movie ID: <strong>{movie_id}</strong></p>
            </div>
        '''
    else:
        logging.error(f"Movie '{movie_name}' added (ID: {movie_id}), but failed to add/update types. Error: {types_insert_result}")
        return render_bulma_notification(f'Movie details added (ID: {movie_id}), but failed to update types. Please check logs.', 'is-warning')

@app.route('/getValidMovies', methods=['POST'])
@login_required(role="manager")
def validMovies():
    show_date = request.form.get('showDate')
    if not show_date:
        return render_bulma_notification('Missing show date.', 'is-warning')
    movies_query = """
        SELECT m.movie_id, m.movie_name, m.length, m.language
        FROM movies m
        WHERE m.show_start <= %s AND m.show_end >= %s
    """
    valid_movies_results = runQuery(movies_query, (show_date, show_date))
    if valid_movies_results is None:
        return render_bulma_notification('Error retrieving movie data.', 'is-danger')
    if not valid_movies_results:
        return render_bulma_notification('No Movies Available for Showing On Selected Date', 'is-info')
    movies_with_types = []
    types_query = "SELECT type1, type2, type3 FROM types WHERE movie_id = %s"
    for movie_row in valid_movies_results:
        movie_id, movie_name, length, language = movie_row
        types_result = runQuery(types_query, (movie_id,), fetch_one=True)
        type_str = "N/A"
        if types_result:
            valid_types = [t for t in types_result if t and t.strip() and t.upper() != 'NUL']
            if valid_types:
                type_str = ' '.join(valid_types)
        movies_with_types.append((movie_id, movie_name, type_str, length, language))
    return render_template('validMovies.html', movies=movies_with_types)

@app.route('/getHallsAvailable', methods=['POST'])
@login_required(role="manager")
def getHalls():
    movie_id_str = request.form.get('movieID')
    show_date = request.form.get('showDate')
    show_time_str = request.form.get('showTime')
    if not all([movie_id_str, show_date, show_time_str]):
        return render_bulma_notification('Missing required information (Movie ID, Date, or Time).', 'is-warning')
    try:
        movie_id = int(movie_id_str)
        new_show_time_int = int(show_time_str)
        len_query = "SELECT length FROM movies WHERE movie_id = %s"
        len_result = runQuery(len_query, (movie_id,), fetch_one=True)
        if not len_result or len_result[0] is None:
            return render_bulma_notification(f'Could not find movie length for ID {movie_id}.', 'is-danger')
        movie_len_min = int(len_result[0])
        new_start_min = (new_show_time_int // 100) * 60 + (new_show_time_int % 100)
        new_end_min = new_start_min + movie_len_min
        existing_shows_query = """
            SELECT s.hall_id, m.length, s.time
            FROM shows s
            JOIN movies m ON s.movie_id = m.movie_id
            WHERE s.Date = %s
        """
        existing_shows = runQuery(existing_shows_query, (show_date,))
        if existing_shows is None:
            return render_bulma_notification('Error retrieving existing show schedule.', 'is-danger')
        unavailable_halls = set()
        for hall_id, existing_len_min, existing_time_int in existing_shows:
            if existing_len_min is None or existing_time_int is None: continue
            existing_start_min = (existing_time_int // 100) * 60 + (existing_time_int % 100)
            existing_end_min = existing_start_min + int(existing_len_min)
            if new_start_min < existing_end_min and new_end_min > existing_start_min:
                unavailable_halls.add(hall_id)
        all_halls_query = "SELECT DISTINCT hall_id, hall_name FROM halls"
        all_halls_results = runQuery(all_halls_query)
        if all_halls_results is None:
            return render_bulma_notification('Error retrieving list of halls.', 'is-danger')
        all_halls = { (row[0], row[1]) for row in all_halls_results }
        available_halls_data = []
        for hall_id, hall_name in all_halls:
            if hall_id not in unavailable_halls:
                available_halls_data.append({"id": hall_id, "name": hall_name})

        if not available_halls_data:
            return render_bulma_notification('No Halls Available On Given Date And Time Slot', 'is-info')
        
        sorted_available_halls = sorted(available_halls_data, key=lambda x: x['id'])
        return render_template('availableHalls.html', halls=sorted_available_halls)
    except ValueError:
        return render_bulma_notification('Invalid numeric input for Movie ID or Time.', 'is-danger')
    except Exception as e:
        logging.error(f"Error getting available halls: {e}")
        return render_bulma_notification('An unexpected error occurred while checking hall availability.', 'is-danger')

@app.route('/insertShow', methods=['POST'])
@login_required(role="manager")
def insertShow():
    hall_id_str = request.form.get('hallID')
    movie_id_str = request.form.get('movieID')
    movie_type = request.form.get('movieType')
    show_date = request.form.get('showDate')
    show_time_str = request.form.get('showTime')
    if not all([hall_id_str, movie_id_str, movie_type, show_date, show_time_str]):
        return render_bulma_notification('Missing required show information.', 'is-warning')
    try:
        hall_id = int(hall_id_str)
        movie_id = int(movie_id_str)
        show_time = int(show_time_str)
        show_id = None
        attempts = 0
        max_attempts = 10
        while attempts < max_attempts:
            show_id = generate_id()
            check_id_query = "SELECT show_id FROM shows WHERE show_id = %s"
            id_exists = runQuery(check_id_query, (show_id,), fetch_one=True)
            if not id_exists: break
            attempts += 1
        else:
            logging.error("Failed to generate a unique show ID.")
            return render_bulma_notification('Error generating unique show ID. Please try again.', 'is-danger')
        assigned_price_id = None
        insert_query = """
            INSERT INTO shows (show_id, movie_id, hall_id, type, time, Date, price_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params = (show_id, movie_id, hall_id, movie_type, show_time, show_date, assigned_price_id)
        insert_result = runQuery(insert_query, params)
        if isinstance(insert_result, list):
            return f'''
                <div class="notification is-success is-light has-text-centered">
                    <p class="is-size-5 has-text-weight-semibold mb-1">Show Successfully Scheduled</p>
                    <p class="is-size-6">Show ID: <strong>{show_id}</strong></p>
                </div>
            '''
        else:
            logging.error(f"Show insertion failed for movie {movie_id} in hall {hall_id}. runQuery returned: {insert_result}")
            return render_bulma_notification('Failed to schedule show. A database error occurred or there might be a conflict.', 'is-danger')
    except ValueError:
        return render_bulma_notification('Invalid numeric input for Hall ID, Movie ID, or Time.', 'is-danger')
    except Exception as e:
        logging.error(f"Error during show insertion: {e}")
        return render_bulma_notification('An unexpected error occurred during show scheduling.', 'is-danger')

@app.route('/getPriceList', methods=['GET'])
@login_required(role="manager")
def priceList():
    query = "SELECT price_id, type, day, price FROM price_listing"
    results = runQuery(query)
    if results is None:
        return render_bulma_notification('Error retrieving price list.', 'is-danger')
    day_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    sorted_results = []
    try:
        sorted_results = sorted(results, key=lambda x: (x[1] if x[1] else '', day_order.index(x[2]) if x[2] in day_order else 99))
    except ValueError as e:
        logging.warning(f"Could not sort price list by day, possibly invalid day name found? Error: {e}. Returning unsorted.")
        sorted_results = results
    return render_template('currentPrices.html', prices=sorted_results)

@app.route('/setNewPrice', methods=['POST'])
@login_required(role="manager")
def setPrice():
    price_id_str = request.form.get('priceID')
    new_price_str = request.form.get('newPrice')
    if not all([price_id_str, new_price_str]):
        return render_bulma_notification('Missing Price ID or New Price value.', 'is-warning')
    try:
        price_id = int(price_id_str)
        new_price = int(new_price_str)
        if new_price < 0:
            return render_bulma_notification('Price cannot be negative.', 'is-danger')
        update_query = "UPDATE price_listing SET price = %s WHERE price_id = %s"
        update_result = runQuery(update_query, (new_price, price_id))
        if isinstance(update_result, list):
            gold_price = int(new_price * 1.5)
            return f'''
                <div class="notification is-success is-light has-text-centered">
                    <p class="is-size-5 has-text-weight-semibold mb-1">Price Successfully Changed</p>
                    <p class="is-size-6">Standard Base Price: ₹ {new_price}</p>
                    <p class="is-size-6">(Calculated Gold Price: ₹ {gold_price})</p>
                </div>
            '''
        else:
            logging.error(f"Price update failed for price_id {price_id}. runQuery returned: {update_result}")
            return render_bulma_notification('Failed to update price due to a database error.', 'is-danger')
    except ValueError:
        return render_bulma_notification('Invalid numeric input for Price ID or New Price.', 'is-danger')
    except Exception as e:
        logging.error(f"Error updating price {price_id_str}: {e}")
        return render_bulma_notification('An unexpected error occurred while updating the price.', 'is-danger')
    
@app.route('/getBookingsByDate', methods=['POST'])
@login_required(role="manager")
def getBookingsByDate():
    show_date_str = request.form.get('date')
    if not show_date_str:
        return render_bulma_notification('Invalid date provided.', 'is-warning')

    try:
        try:
            show_date_obj = datetime.strptime(show_date_str, '%Y/%m/%d')
            show_date_sql = show_date_obj.strftime('%Y-%m-%d')
        except ValueError:
             show_date_obj = datetime.strptime(show_date_str, '%Y-%m-%d')
             show_date_sql = show_date_obj.strftime('%Y-%m-%d')
    except ValueError:
        logging.error(f"Invalid date format received for booking lookup: {show_date_str}")
        return render_bulma_notification('Invalid date format. Please use YYYY/MM/DD or YYYY-MM-DD.', 'is-danger')

    query = """
        SELECT
            b.booking_ref,         
            c.customer_name,      
            c.customer_phone,     
            m.movie_name,          
            s.time,                
            s.show_id,             
            h.hall_name,           
            COUNT(bt.ticket_no) as num_tickets 
        FROM bookings b            
        JOIN customers c ON b.customer_id = c.customer_id 
        JOIN booked_tickets bt ON b.booking_ref = bt.booking_ref 
        JOIN shows s ON bt.show_id = s.show_id         
        JOIN movies m ON s.movie_id = m.movie_id         
        JOIN halls h ON s.hall_id = h.hall_id            
        WHERE s.Date = %s         
        GROUP BY b.booking_ref, c.customer_name, c.customer_phone, s.show_id, m.movie_name, s.time, h.hall_name
        ORDER BY s.time, b.booking_ref
    """

    results = runQuery(query, (show_date_sql,))

    if results is None:
        return render_bulma_notification('Error retrieving booking data.', 'is-danger')
    if not results:
        return render_bulma_notification('No Bookings Found for this Date', 'is-info')

    bookings_formatted = []
    for row in results:
        booking_ref, cust_name, cust_phone, movie_name, time_int, show_id, hall_name, num_tickets = row
        hour, minute_str = format_time_tuple(time_int)
        show_time_formatted = f"{hour}:{minute_str}" if hour is not None else "N/A"
        bookings_formatted.append({
            "booking_ref": booking_ref,
            "customer_name": cust_name if cust_name else "N/A",
            "customer_phone": cust_phone if cust_phone else "N/A",
            "movie_name": movie_name,
            "show_time": show_time_formatted,
            "hall_name": hall_name,
            "num_tickets": num_tickets
        })

    return render_template('groupedBookings.html', bookings=bookings_formatted, booking_date=show_date_sql)

def db_no_to_seat_code(seat_db_no):
    if seat_db_no is None:
        return "N/A"

    seat_class = 'standard'
    relative_seat_no = seat_db_no

    if seat_db_no > GOLD_SEAT_THRESHOLD:
        seat_class = 'gold'
        relative_seat_no = seat_db_no - GOLD_SEAT_THRESHOLD

    if relative_seat_no <= 0:
        return "Invalid"

    seat_index_0 = relative_seat_no - 1

    row_index = seat_index_0 // SEATS_PER_ROW
    col_index = seat_index_0 % SEATS_PER_ROW

    row_letter = chr(ord('A') + row_index)
    col_number = col_index + 1

    return f"{row_letter}{col_number}"
    
@app.route('/ticket/<string:booking_ref>')
@login_required(role="any")
def show_ticket(booking_ref):
    query = """
        SELECT
            bt.ticket_no, bt.seat_no,
            b.booking_time,
            c.customer_name, c.customer_phone,
            s.Date, s.time, s.type as show_type, s.show_id,
            m.movie_name, m.length,
            h.hall_id, h.hall_name,
            pl.price as base_standard_price
        FROM booked_tickets bt
        JOIN bookings b ON bt.booking_ref = b.booking_ref
        JOIN customers c ON b.customer_id = c.customer_id
        JOIN shows s ON bt.show_id = s.show_id
        JOIN movies m ON s.movie_id = m.movie_id
        JOIN halls h ON s.hall_id = h.hall_id
        LEFT JOIN price_listing pl ON s.price_id = pl.price_id
        WHERE bt.booking_ref = %s
        ORDER BY bt.seat_no
    """

    results = runQuery(query, (booking_ref,))

    if not results:
        return render_template('ticket.html', data=None, error="Ticket not found or invalid reference.")

    ticket_data = {
        "booking_ref": booking_ref,
        "tickets": [],
        "show_info": None,
        "qr_code_data": None,
        "pricing_info": None
    }
    total_pre_tax_price = 0
    processed_ticket_nos = set()
    qr_code_content_list = []
    base_price_for_gst_calc = None

    for row in results:
        (ticket_no, seat_db_no, booking_time, cust_name, cust_phone, show_date, show_time_int, show_type, show_id, movie_name, movie_len, hall_id, hall_name, base_price) = row

        if ticket_no in processed_ticket_nos:
            continue

        if ticket_data["show_info"] is None:
             hour, minute_str = format_time_tuple(show_time_int)
             base_price_for_gst_calc = base_price if base_price is not None else 0
             ticket_data["show_info"] = {
                 "movie_name": movie_name,
                 "show_type": show_type,
                 "date": show_date.strftime('%Y-%m-%d') if show_date else "N/A",
                 "time": f"{hour}:{minute_str}" if hour is not None else "N/A",
                 "hall_name": hall_name,
                 "customer_name": cust_name,
                 "customer_phone": cust_phone,
                 "show_id": show_id,
                 "booking_time": booking_time.strftime('%Y-%m-%d %H:%M:%S') if booking_time else "N/A"
             }

        seat_code_display = db_no_to_seat_code(seat_db_no)
        seat_class = 'Standard'
        ticket_pre_tax_price = base_price if base_price is not None else 0
        if seat_db_no > GOLD_SEAT_THRESHOLD:
             seat_class = 'Gold'
             if base_price is not None:
                ticket_pre_tax_price = int(base_price * 1.5)

        seat_display_str = f"{seat_code_display}({seat_class[0]})"
        ticket_info = {
            "ticket_no": ticket_no,
            "seat_display": f"{seat_code_display} ({seat_class})",
            "price": ticket_pre_tax_price,
            "class": seat_class
        }
        ticket_data["tickets"].append(ticket_info)
        qr_code_content_list.append(f"T{ticket_no}:S-{seat_display_str}")

        total_pre_tax_price += ticket_pre_tax_price
        processed_ticket_nos.add(ticket_no)

    cgst_rate = 0
    sgst_rate = 0
    cgst_amount = 0
    sgst_amount = 0
    final_total_price = total_pre_tax_price

    if base_price_for_gst_calc is not None:
         if base_price_for_gst_calc > 100:
             gst_rate_total = 0.18
         else:
             gst_rate_total = 0.12

         cgst_rate = gst_rate_total / 2
         sgst_rate = gst_rate_total / 2

         cgst_amount = round(total_pre_tax_price * cgst_rate, 2)
         sgst_amount = round(total_pre_tax_price * sgst_rate, 2)
         final_total_price = round(total_pre_tax_price + cgst_amount + sgst_amount, 2)

    ticket_data["pricing_info"] = {
        "pre_tax_total": round(total_pre_tax_price, 2),
        "cgst_rate_percent": int(cgst_rate * 100),
        "cgst_amount": cgst_amount,
        "sgst_rate_percent": int(sgst_rate * 100),
        "sgst_amount": sgst_amount,
        "final_total": final_total_price
    }

    if ticket_data["show_info"]:
        qr_data_string = f"Ref:{booking_ref}\n"
        qr_data_string += f"Show:{ticket_data['show_info']['show_id']}\n"
        qr_data_string += f"Date:{ticket_data['show_info']['date']}\n"
        qr_data_string += ";".join(qr_code_content_list)

        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=6,
                border=4,
            )
            qr.add_data(qr_data_string)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            ticket_data["qr_code_data"] = f"data:image/png;base64,{img_base64}"

        except Exception as e:
            logging.error(f"Failed to generate QR code for booking {booking_ref}: {e}")
            ticket_data["qr_code_data"] = None 

    return render_template('ticket.html', data=ticket_data)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)