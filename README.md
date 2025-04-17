# Theatre Management and Ticketing System

A basic Theatre Management and Ticketing System created as an Database Management System (UCS310) project at Thapar Institute of Engineering and Technology.

## Prerequisites

* **Python 3.x** installed.
* **MySQL Server** installed and running.
* **pip** (Python package installer).

## Setup Instructions

1.  **Clone the Repository (or place files):**
    Ensure you have all the project files (`app.py`, `db.sql`, `templates/`, `static/` directory, etc.) in a single project folder.

2.  **Install Dependencies:**
    Open your terminal or command prompt, navigate to the project folder, and install the required Python packages using pip:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup MySQL Database:**
    * Log in to your MySQL server as a user with privileges to create databases (e.g., root or another admin user). You can use the command line or a GUI tool like MySQL Workbench.
        ```bash
        # Example using command line
        mysql -u your_mysql_user -p
        ```
    * Create the database named `db_theatre`:
        ```sql
        CREATE DATABASE db_theatre;
        ```
    * Select the newly created database:
        ```sql
        USE db_theatre;
        ```
    * Run the `db.sql` script provided with the project to create the necessary tables, triggers, and initial data. Make sure you are still connected to the `db_theatre` database.
        ```bash
        # Example using command line (run from your OS terminal, not MySQL prompt)
        mysql -u your_mysql_user -p db_theatre < db.sql
        ```
        Alternatively, open the `db.sql` file in your MySQL GUI tool and execute its contents against the `db_theatre` database.

4.  **Configure Database Credentials (.env file):**
    * Create a file named `.env` in the root of your project directory.
    * Add your MySQL database credentials to this file:
        ```dotenv
        # .env file
        DB_DATABASE=db_theatre
        DB_USER=your_mysql_user
        DB_PASSWORD=your_mysql_password
        ```
    * Replace `your_mysql_user` and `your_mysql_password` with the actual username and password for your MySQL user that has access to the `db_theatre` database.

5.  **Run the Application:**
    Open your terminal or command prompt, navigate to the project folder, and run the Flask application:
    ```bash
    python app.py
    ```
    The application should now be running, typically at `http://127.0.0.1:5000/` or `http://0.0.0.0:5000/`.

## Usage

* Access the application via your web browser.
* Log in using the predefined credentials:
    * **Cashier:** username `cashier`, password `cashier`
    * **Manager:** username `manager`, password `manager`
* Follow the on-screen options to book tickets (Cashier) or manage movies, shows, and pricing (Manager).