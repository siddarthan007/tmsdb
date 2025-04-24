USE db_theatre;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS booked_tickets;
DROP TABLE IF EXISTS shows;
DROP TABLE IF EXISTS types;
DROP TABLE IF EXISTS price_listing;
DROP TABLE IF EXISTS movies;
DROP TABLE IF EXISTS halls;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS bookings;
DROP TRIGGER IF EXISTS set_show_price_on_insert;
DROP PROCEDURE IF EXISTS delete_old_records;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE halls (
    hall_id INT PRIMARY KEY,
    hall_name VARCHAR(50) NOT NULL
);

CREATE TABLE hall_classes (
     hall_class_id INT AUTO_INCREMENT PRIMARY KEY,
     hall_id INT NOT NULL,
     class VARCHAR(10) NOT NULL,
     no_of_seats INT NOT NULL,
     FOREIGN KEY (hall_id) REFERENCES halls(hall_id) ON DELETE CASCADE,
     UNIQUE KEY idx_hall_class_unique (hall_id, class)
);

CREATE TABLE movies (
    movie_id INT PRIMARY KEY,
    movie_name VARCHAR(40) NOT NULL,
    length INT,
    language VARCHAR(10),
    show_start DATE,
    show_end DATE
);

CREATE TABLE price_listing (
    price_id INT PRIMARY KEY,
    type VARCHAR(3) NOT NULL,
    day VARCHAR(10) NOT NULL,
    price INT NOT NULL
);

CREATE TABLE shows (
    show_id INT PRIMARY KEY,
    movie_id INT,
    hall_id INT,
    type VARCHAR(3),
    time INT,
    Date DATE,
    price_id INT NULL,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (hall_id) REFERENCES halls(hall_id),
    FOREIGN KEY (price_id) REFERENCES price_listing(price_id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE types (
    movie_id INT PRIMARY KEY,
    type1 VARCHAR(3),
    type2 VARCHAR(3),
    type3 VARCHAR(3),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
);

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL
);

CREATE TABLE customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    customer_phone VARCHAR(20) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE bookings (
    booking_ref VARCHAR(20) PRIMARY KEY,
    customer_id INT NOT NULL,
    booking_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE booked_tickets (
    ticket_no INT PRIMARY KEY,
    show_id INT NOT NULL,
    seat_no INT NOT NULL,
    booking_ref VARCHAR(20) NULL,
    FOREIGN KEY (show_id) REFERENCES shows(show_id) ON DELETE CASCADE,
    FOREIGN KEY (booking_ref) REFERENCES bookings(booking_ref) ON DELETE CASCADE,
    UNIQUE KEY `unique_show_seat` (`show_id`, `seat_no`),
    INDEX `idx_booking_ref` (`booking_ref`)
);

INSERT INTO users (user_id, username, password_hash, role) VALUES
(1, 'cashier', 'scrypt:32768:8:1$xLrcHhakt8JABBCX$cdd37c183dd10698a17f31683fb4630d94d5a185c4e6f2bf9eb313d1d0d9ff25a473771c466918ae0180bfd9d19d58f65ae4c46e222201b7b81d4fe1295a682b', 'cashier'), 
(2, 'manager', 'scrypt:32768:8:1$a2vR5ywzz5K38sBA$07d2c2bb6f40eb25d519fda46f139f8fd636189b7bd0bdcad059ef6a16ef9268ffbe6e6bc41257040fe05b63015474889e42ba76e0a91b47e1b1517e8cd0e9ee', 'manager'); 

INSERT INTO halls (hall_id, hall_name) VALUES
(1, 'Audi 1'),
(2, 'Audi 2'),
(3, 'Audi 3');

INSERT INTO hall_classes (hall_id, class, no_of_seats) VALUES
(1, 'gold', 35),
(1, 'standard', 75),
(2, 'gold', 27),
(2, 'standard', 97),
(3, 'gold', 26),
(3, 'standard', 98);

INSERT INTO price_listing (price_id, type, day, price) VALUES
(1, '2D', 'Monday', 210), (2, '3D', 'Monday', 295), (3, '4DX', 'Monday', 380),
(4, '2D', 'Tuesday', 210), (5, '3D', 'Tuesday', 295), (6, '4DX', 'Tuesday', 380),
(7, '2D', 'Wednesday', 210), (8, '3D', 'Wednesday', 295), (9, '4DX', 'Wednesday', 380),
(10, '2D', 'Thursday', 210), (11, '3D', 'Thursday', 295), (12, '4DX', 'Thursday', 380),
(13, '2D', 'Friday', 320), (14, '3D', 'Friday', 335), (15, '4DX', 'Friday', 495),
(16, '2D', 'Saturday', 320), (17, '3D', 'Saturday', 335), (18, '4DX', 'Saturday', 495),
(19, '2D', 'Sunday', 320), (20, '3D', 'Sunday', 335), (21, '4DX', 'Sunday', 495);

DELIMITER //

CREATE TRIGGER set_show_price_on_insert
BEFORE INSERT ON shows
FOR EACH ROW
BEGIN
    SET NEW.price_id = (
        SELECT price_id
        FROM price_listing
        WHERE type = NEW.type AND day = DAYNAME(NEW.Date)
        LIMIT 1
    );
END;
//

DELIMITER ;


DELIMITER //

CREATE PROCEDURE delete_old_records()
BEGIN
    DECLARE today DATE;
    SET today = CURDATE();

    DELETE FROM shows
    WHERE Date < today;

    DELETE FROM shows
    WHERE movie_id IN (
        SELECT movie_id
        FROM movies
        WHERE show_end < today
    );

    DELETE FROM movies
    WHERE show_end < today;
END;
//

DELIMITER ;


SELECT 'Database schema and base data setup complete.' AS Status;