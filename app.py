import mysql.connector
from dotenv import dotenv_values
from mysql.connector import Error
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from random import randint
import logging
import os
from functools import wraps

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

app.secret_key = os.urandom(24)

config = dotenv_values(".env")

DB_HOST = 'localhost'
DB_DATABASE = config.get('DB_DATABASE', 'your_default_db_name')
DB_USER = config.get('DB_USER', 'your_default_user')
DB_PASSWORD = config.get('DB_PASSWORD', 'your_default_password')

GOLD_SEAT_THRESHOLD = 1000

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
    return randint(1_000_000_000, 9_999_999_999)

def runQuery(query, params=None, fetch_one=False):
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
                return redirect(url_for('renderLoginPage'))
            if role != "any" and session.get('user_role') != role:
                return "Access Denied: You do not have permission to access this page.", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def renderLoginPage():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def verifyAndRenderRespective():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        return render_template('loginFail.html', message="Username or password cannot be empty.")
    try:
        if username == 'cashier' and password == 'cashier':
            session['username'] = username
            session['user_role'] = 'cashier'
            logging.info(f"User {username} logged in as cashier.")
            return render_template('cashier.html')
        elif username == 'manager' and password == 'manager':
            session['username'] = username
            session['user_role'] = 'manager'
            logging.info(f"User {username} logged in as cashier.")
            return render_template('manager.html')
        else:
            session.pop('username', None)
            session.pop('user_role', None)
            return render_template('loginFail.html', message="Invalid username or password.")
    except Exception as e:
        logging.error(f"Error during login verification: {e}")
        return render_template('loginFail.html', message="An internal server error occurred during login.")
    
@app.route('/logout')
@login_required(role="any")
def logout():
    session.pop('user_role', None)
    session.pop('username', None)
    return redirect(url_for('renderLoginPage'))

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
    gold_seats = []
    standard_seats = []
    for i in range(1, total_gold + 1):
        seat_db_no = i + GOLD_SEAT_THRESHOLD
        status = 'disabled' if seat_db_no in booked_seat_nos else ''
        gold_seats.append([i, status])
    for i in range(1, total_standard + 1):
        seat_db_no = i
        status = 'disabled' if seat_db_no in booked_seat_nos else ''
        standard_seats.append([i, status])
    return render_template('seating.html', goldSeats=gold_seats, standardSeats=standard_seats)

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
    show_id_str = request.form.get('showID')
    seat_no_str = request.form.get('seatNo')
    seat_class = request.form.get('seatClass')
    if not all([show_id_str, seat_no_str, seat_class]):
        return render_bulma_notification('Missing booking information (Show ID, Seat No, or Class).', 'is-warning')
    try:
        show_id = int(show_id_str)
        seat_display_no = int(seat_no_str)
        if seat_class.lower() == 'gold':
            seat_db_no = seat_display_no + GOLD_SEAT_THRESHOLD
        elif seat_class.lower() == 'standard':
            seat_db_no = seat_display_no
        else:
            return render_bulma_notification('Invalid seat class specified.', 'is-danger')
        ticket_no = None
        attempts = 0
        max_attempts = 10
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
        insert_query = "INSERT INTO booked_tickets (ticket_no, show_id, seat_no) VALUES (%s, %s, %s)"
        insert_result = runQuery(insert_query, (ticket_no, show_id, seat_db_no))
        if isinstance(insert_result, list) and not insert_result:
            return f'''
                <div class="notification is-success is-light has-text-centered">
                    <p class="is-size-5 has-text-weight-semibold mb-1">Ticket Successfully Booked!</p>
                    <p class="is-size-6">Ticket Number: <strong>{ticket_no}</strong></p>
                    <p class="is-size-7">Seat: {seat_display_no} ({seat_class.capitalize()})</p>
                </div>
            '''
        else:
            logging.error(f"Booking insertion potentially failed for show {show_id}, seat {seat_db_no}. runQuery returned: {insert_result}")
            return render_bulma_notification('Booking Failed. The seat might have just been taken, or a database error occurred.', 'is-danger')
    except ValueError:
        return render_bulma_notification('Invalid numeric input for Show ID or Seat Number.', 'is-danger')
    except Exception as e:
        logging.error(f"Error during booking insertion: {e}")
        return render_bulma_notification('An unexpected error occurred during booking.', 'is-danger')

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
        all_halls_query = "SELECT DISTINCT hall_id FROM halls"
        all_halls_results = runQuery(all_halls_query)
        if all_halls_results is None:
            return render_bulma_notification('Error retrieving list of halls.', 'is-danger')
        all_hall_ids = {row[0] for row in all_halls_results}
        available_halls = all_hall_ids.difference(unavailable_halls)
        if not available_halls:
            return render_bulma_notification('No Halls Available On Given Date And Time Slot', 'is-info')
        sorted_available_halls = sorted(list(available_halls))
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
                    <p class="is-size-7">(Price needs to be assigned if not automatic)</p>
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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)