var username = null;
var password = null;
var date = null;
var movieID = null;
var type = null;
var seatNo = null;
var seatClass = null;
let selectedSeats = [];
var movieTime = null;
var showID = null;
var startShowing = null;
var endShowing = null;
var showTime = null;
var showDate = null;
var priceID = null;

function createNotification(message, type = 'is-danger') {
    return `<div class="notification ${type} is-light p-2 mb-3"> ${message} </div>`;
}

function logoutUser() {
    window.location.href = '/logout';
}

function getMoviesShowingOnDate(mdate) {
    date = mdate;
    console.log("Fetching movies for date:", date);
    $('#movies-on-date').html('<progress class="progress is-small is-info" max="100">15%</progress>');

    $.ajax({
        type: 'POST',
        url: '/getMoviesShowingOnDate',
        data: { 'date': date },
        success: function(response) {
            $('#movies-on-date').html(response);
            $('#movies-on-date button').addClass('button is-link m-1');
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("getMoviesShowingOnDate AJAX error:", textStatus, errorThrown);
            $('#movies-on-date').html(createNotification('Could not load movies. Please try again.', 'is-warning'));
        }
    });
}

function selectMovie(movID, mtype) {
    movieID = movID;
    type = mtype;
    console.log("Selected Movie:", movieID, "Type:", type, "Date:", date);
    $('#timings-for-movie').html('<progress class="progress is-small is-info" max="100">15%</progress>');

    $.ajax({
        type: 'POST',
        url: '/getTimings',
        data: {
            'date': date,
            'movieID': movieID,
            'type': type
        },
        success: function(response) {
            $('#movies-on-date button');
            $('#timings-for-movie').html(response);
            $('#timings-for-movie button').addClass('button is-primary m-1');
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("selectMovie AJAX error:", textStatus, errorThrown);
            $('#timings-for-movie').html(createNotification('Could not load timings. Please try again.', 'is-warning'));
        }
    });
}

function selectTiming(mtime) {
    movieTime = mtime;
    console.log("Selected Timing:", movieTime, "for Show:", movieID, type, date);
    $('#available-seats').html('<progress class="progress is-small is-info" max="100">15%</progress>');

    $.ajax({
        type: 'POST',
        url: '/getShowID',
        dataType: 'json',
        data: {
            'date': date,
            'movieID': movieID,
            'type': type,
            'time': movieTime
        },
        success: function(response) {
            if (response && response.showID) {
                $('#timings-for-movie button');
                showID = response.showID;
                console.log("Got showID:", showID);
                getSeats();
            } else {
                console.error("Could not retrieve showID from response:", response);
                $('#available-seats').html(createNotification('Error finding show details. Please reselect.', 'is-danger'));
            }
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("selectTiming AJAX error:", textStatus, errorThrown);
            $('#available-seats').html(createNotification('Could not fetch show details. Please try again.', 'is-warning'));
        }
    });
}

function getSeats() {
    console.log("Getting seats for showID:", showID);
    if (!showID) {
        $('#available-seats').html(createNotification('Invalid Show selected. Please start over.', 'is-danger'));
        return;
    }
    $('#available-seats').html('<progress class="progress is-small is-info" max="100">15%</progress>');

    $.ajax({
        type: 'POST',
        url: '/getAvailableSeats',
        data: { 'showID': showID },
        success: function(response) {
            $('#available-seats').html(response);
            $('#available-seats .seat-button').addClass('button m-1 is-small');
            $('#available-seats .seat-available').addClass('is-outlined is-primary');
            $('#available-seats .seat-booked').addClass('is-danger');
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("getSeats AJAX error:", textStatus, errorThrown);
            $('#available-seats').html(createNotification('Could not load seating plan. Please try again.', 'is-warning'));
        }
    });
}

function selectSeat(seatCode, seatClass, seatDbNo) {
    const seatIndex = selectedSeats.findIndex(seat => seat.db_no === seatDbNo);
    const seatButton = document.getElementById(`seat-${seatClass}-${seatCode}`);

    if (!seatButton) return;

    if (seatIndex > -1) {
        selectedSeats.splice(seatIndex, 1);
        seatButton.classList.remove('is-success');
        seatButton.classList.add('is-warning', 'is-light');
         if (seatClass === 'standard') {
             seatButton.classList.remove('is-warning');
             seatButton.classList.add('is-info', 'is-light');
         }
    } else {
        selectedSeats.push({ code: seatCode, class: seatClass, db_no: seatDbNo });
        seatButton.classList.remove('is-light', 'is-warning', 'is-info');
        seatButton.classList.add('is-success');
    }

    console.log("Selected Seats:", selectedSeats);
    updatePriceAndConfirmButton();
}

function updatePriceAndConfirmButton() {
    $('#price-and-confirm').html('<progress class="progress is-small is-info" max="100">15%</progress>');

    if (selectedSeats.length === 0) {
         $('#price-and-confirm').html('<p class="has-text-centered">Please select one or more seats.</p>');
         return;
    }
    if (!showID){
         $('#price-and-confirm').html(createNotification('Error: Show ID not set. Please re-select movie/time.', 'is-danger'));
         return;
    }

    $.ajax({
        type: 'POST',
        url: '/getTotalPrice',
        contentType: 'application/json',
        data: JSON.stringify({
            'showID': showID,
            'seats':  selectedSeats.map(s => ({ seatCode: s.code, seatClass: s.class }))
        }),
        success: function(response) {
            $('#price-and-confirm').html(response);
            let confirmButton = $('#confirm-booking-button');
            if (confirmButton.length) {
                 confirmButton.prop('disabled', selectedSeats.length === 0);
            }
        },
        error: function(jqXHR) {
            let errorMsg = 'Could not retrieve total price.';
            if (jqXHR.responseJSON && jqXHR.responseJSON.error) {
                errorMsg = jqXHR.responseJSON.error;
            }
            $('#price-and-confirm').html(createNotification(errorMsg, 'is-warning'));
        }
    });
}

function confirmBooking() {
    const customerName = $('#customerNameInput').val();
    const customerPhone = $('#customerPhoneInput').val();

    console.log("Confirming booking for Seats:", selectedSeats, "Show:", showID);

    if (!showID || selectedSeats.length === 0) {
        $('#price-and-confirm').append(createNotification('Please select a show and at least one seat.', 'is-warning'));
        return;
    }

    $('#confirm-booking-button').addClass('is-loading');

    $.ajax({
        type: 'POST',
        url: '/insertBooking',
        contentType: 'application/json',
        data: JSON.stringify({
            'showID': showID,
            'selectedSeats': selectedSeats,
            'customerName': customerName,
            'customerPhone': customerPhone
        }),
        success: function(response) {
             $('#available-seats button');
            $('#price-and-confirm').html(response);
        },
        error: function(jqXHR, textStatus, errorThrown) {
            let errorMsg = 'Booking failed due to a network or server error.';
             if (jqXHR.responseJSON && jqXHR.responseJSON.error) {
                 errorMsg = jqXHR.responseJSON.error;
             } else if (jqXHR.responseText) {
                 errorMsg = jqXHR.responseText;
             }
            console.error("confirmBooking AJAX error:", textStatus, errorThrown, jqXHR.responseText);
             $('#price-and-confirm').append(createNotification(`Booking Failed: ${errorMsg}`, 'is-danger'));
             $('#confirm-booking-button').prop('disabled', false).removeClass('is-loading'); 
        }
    });
}

function viewBookedTickets() {
    console.log("Manager action: View Booked Tickets");
    $('#manager-dynamic-1, #manager-dynamic-2, #manager-dynamic-3, #manager-dynamic-4, #manager-dynamic-5').html('');
    $('#options button');
    $('#options button.is-info').removeClass('is-info').addClass('is-light');
    $('#options button[onclick="viewBookedTickets()"]').removeClass('is-light').addClass('is-info');
    $('#manager-dynamic-1').html(`
        <div class="box">
            <h4 class="title is-5 mb-4 has-text-light">View Bookings By Date</h4>
            <div class="field">
                <label class="label has-text-light" for="datepicker-manager-1">Select Date</label>
                <div class="control has-icons-left">
                    <input class="input" id="datepicker-manager-1" placeholder="Pick a date">
                    <span class="icon is-small is-left"><i class="fas fa-calendar-alt"></i></span>
                </div>
            </div>
            <p class="help has-text-grey-light">Select a date to see all booking transactions made for shows on that day.</p>
        </div>`);

    $('#datepicker-manager-1').pickadate({
        formatSubmit: 'yyyy/mm/dd',
        format: 'd mmmm, yyyy',
        hiddenName: true,
        klass: { input: 'input' },
        onSet: function(event) {
            if (event.select) {
                const selectedDate = this.get('select', 'yyyy/mm/dd');
                $('#datepicker-manager-view-bookings');
                fetchGroupedBookings(selectedDate);
            }
        },
        onClose: function() {
            $('#options button').prop('disabled', false);
        }
    });
    $('#datepicker-manager-view-bookings').trigger('focus');
}

function fetchGroupedBookings(selectedDate) {
    console.log("Manager: Fetching grouped bookings for date:", selectedDate);
    $('#manager-dynamic-2').html('<progress class="progress is-small is-info" max="100">15%</progress>');
    $('#manager-dynamic-3, #manager-dynamic-4, #manager-dynamic-5').html('');

    $.ajax({
        type: 'POST',
        url: '/getBookingsByDate',
        data: { 'date': selectedDate },
        success: function(response) {
            $('#manager-dynamic-2').html(response);
            $('#options button').prop('disabled', false);
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("fetchGroupedBookings AJAX error:", textStatus, errorThrown);
            $('#manager-dynamic-2').html(createNotification('Could not load bookings for this date.', 'is-warning'));
            $('#options button').prop('disabled', false);
            $('#datepicker-manager-view-bookings').prop('disabled', false);
        }
    });
}

function getShowsShowingOnDate(mdate) {
    date = mdate;
    console.log("Manager: Fetching shows for date:", date);
    $('#manager-dynamic-2').html('<progress class="progress is-small is-info" max="100">15%</progress>');

    $.ajax({
        type: 'POST',
        url: '/getShowsShowingOnDate',
        data: { 'date': date },
        success: function(response) {
            $('#manager-dynamic-2').html(response);
            $('#manager-dynamic-2 button').addClass('button is-link m-1');
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("getShowsShowingOnDate AJAX error:", textStatus, errorThrown);
            $('#manager-dynamic-2').html(createNotification('Could not load shows for this date.', 'is-warning'));
        }
    });
    $('#manager-dynamic-3, #manager-dynamic-4, #manager-dynamic-5').html('');
}

function selectShow(mshowID) {
    showID = mshowID;
    console.log("Manager: Selecting show:", showID, "to view bookings.");
    $('#manager-dynamic-3').html('<progress class="progress is-small is-info" max="100">15%</progress>');

    $.ajax({
        type: 'POST',
        url: '/getBookedWithShowID',
        data: { 'showID': showID },
        success: function(response) {
            $('#manager-dynamic-2 button');
            $('#manager-dynamic-3').html(response);
            $('#manager-dynamic-3 table').addClass('table is-bordered is-striped is-narrow is-hoverable is-fullwidth');
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("selectShow AJAX error:", textStatus, errorThrown);
            $('#manager-dynamic-3').html(createNotification('Could not load bookings for this show.', 'is-warning'));
        }
    });
    $('#manager-dynamic-4, #manager-dynamic-5').html('');
}

function insertMovie() {
    console.log("Manager action: Insert New Movie");
    $('#options button');
    $('#options button.is-info').removeClass('is-info').addClass('is-light');
    $('#manager-dynamic-1').html('<progress class="progress is-small is-info" max="100">15%</progress>');

    $.ajax({
        type: 'GET',
        url: '/fetchMovieInsertForm',
        success: function(response) {
            $('#manager-dynamic-1').html('<div class="box">' + response + '</div>');
            $('#manager-dynamic-1 form .field').addClass('mb-3');
            $('#manager-dynamic-1 form .label').addClass('label');
            $('#manager-dynamic-1 form .input').addClass('input');
            $('#manager-dynamic-1 form .button').addClass('button is-primary');
            $('#manager-dynamic-1 form .control').addClass('control');
            var pickerOptions = {
                formatSubmit: 'yyyy/mm/dd',
                hiddenName: true,
                klass: { input: 'input' }
            };
            $('#datepicker-manager-2').pickadate({
                ...pickerOptions,
                onSet: function(event) {
                    if (event.select) {
                        startShowing = this.get('select', 'yyyy/mm/dd');
                        console.log("Start date set:", startShowing);
                        $(this.$node).removeClass('is-danger').addClass('is-success');
                    }
                }
            });
            $('#datepicker-manager-3').pickadate({
                ...pickerOptions,
                onSet: function(event) {
                    if (event.select) {
                        endShowing = this.get('select', 'yyyy/mm/dd');
                        console.log("End date set:", endShowing);
                        $(this.$node).removeClass('is-danger').addClass('is-success');
                    }
                }
            });
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("insertMovie (fetch form) AJAX error:", textStatus, errorThrown);
            $('#manager-dynamic-1').html(createNotification('Could not load the movie form. Please try again.', 'is-warning'));
        }
    });
    $('#manager-dynamic-2, #manager-dynamic-3, #manager-dynamic-4, #manager-dynamic-5').html('');
    $('#manager-dynamic-1').closest('.section').removeClass('is-hidden');
}

function filledMovieForm() {
    console.log("Manager: Submitting new movie form");
    $('#manager-dynamic-2').html('');
    var movieName = $('input[name="movieName"]').val();
    var movieLenStr = $('input[name="movieLen"]').val();
    var movieLang = $('input[name="movieLang"]').val();
    var movieTypesStr = $('input[name="movieTypes"]').val().toUpperCase().trim();
    var startDateSubmit = $('#datepicker-manager-2').val();
    var endDateSubmit = $('#datepicker-manager-3').val();
    startShowing = startDateSubmit;
    endShowing = endDateSubmit;
    var errors = [];
    var $form = $('#manager-dynamic-1 form');
    $form.find('.input, .textarea').removeClass('is-danger');
    $form.find('.help.is-danger').remove();

    function addError(fieldSelector, message) {
        errors.push(message);
        let $field = $form.find(fieldSelector);
        $field.addClass('is-danger');
        let $control = $field.closest('.control');
        if ($control.length) {
            $control.append(`<p class="help is-danger">${message}</p>`);
        }
    }

    if (!movieName) addError('input[name="movieName"]', "Movie Name is required.");
    if (!movieLang) addError('input[name="movieLang"]', "Movie Language is required.");
    if (!movieTypesStr) addError('input[name="movieTypes"]', "Movie Types are required.");
    if (!startShowing) addError('#datepicker-manager-2', "Premiere Date is required.");
    if (!endShowing) addError('#datepicker-manager-3', "Last Showing Date is required.");
    if (!movieLenStr) {
        addError('input[name="movieLen"]', "Movie Length is required.");
    } else if (!$.isNumeric(movieLenStr)) {
        addError('input[name="movieLen"]', "Movie Length must be a number (in minutes).");
    } else if (parseInt(movieLenStr, 10) <= 0) {
        addError('input[name="movieLen"]', "Movie Length must be a positive number.");
    }
    if (startShowing && endShowing && Date.parse(startShowing) > Date.parse(endShowing)) {
        addError('#datepicker-manager-3', "Last Date must be on or after Premiere Date.");
    }
    var types = movieTypesStr.split(' ');
    var allowedTypes = ['2D', '3D', '4DX'];
    var validTypes = types.every(function(t) { return allowedTypes.includes(t); });
    if (!validTypes && movieTypesStr) {
        addError('input[name="movieTypes"]', "Invalid Format (use space-separated: 2D, 3D, 4DX).");
    }

    if (errors.length > 0) {
        let errorHtml = `<div class="notification is-danger is-light mb-3">
                            <strong>Please Correct The Highlighted Fields.</strong>
                         </div>`;
        $('#manager-dynamic-2').html(errorHtml);
    } else {
        var movieLen = parseInt(movieLenStr, 10);
        console.log("Submitting Movie:", movieName, movieLen, movieLang, movieTypesStr, startShowing, endShowing);
        $form.find('button').addClass('is-loading');

        $.ajax({
            type: 'POST',
            url: '/insertMovie',
            data: {
                'movieName': movieName,
                'movieLen': movieLen,
                'movieLang': movieLang,
                'types': movieTypesStr,
                'startShowing': startShowing,
                'endShowing': endShowing
            },
            success: function(response) {
                $('#manager-dynamic-1 input, #manager-dynamic-1 select, #manager-dynamic-1 button');
                $form.find('button').removeClass('is-loading');
                $('#manager-dynamic-2').html(response);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                console.error("filledMovieForm AJAX error:", textStatus, errorThrown);
                $('#manager-dynamic-2').html(createNotification('Failed to submit movie details. Please try again.', 'is-danger'));
                $form.find('button').removeClass('is-loading');
            }
        });
    }
    $('#manager-dynamic-3, #manager-dynamic-4, #manager-dynamic-5').html('');
}

function createShow() {
    console.log("Manager action: Create Show");
    $('#options button');
    $('#options button.is-info').removeClass('is-info').addClass('is-light');
    $('#manager-dynamic-1').html(`
        <div class="box">
            <h4 class="title is-5 mb-4">Create New Show</h4>
            <div class="field">
                <label class="label" for="datepicker-manager-create-show">Select Show Date</label>
                <div class="control">
                    <input class="input" id="datepicker-manager-create-show" placeholder="Pick a date">
                </div>
            </div>
            <div class="field">
                <label class="label" for="timepicker-manager-create-show">Select Show Time</label>
                <div class="control">
                    <input class="input" id="timepicker-manager-create-show" placeholder="Pick a time">
                </div>
            </div>
            <div class="field">
                <div class="control">
                    <button class="button is-info" onclick="getValidMovies()">Find Available Movies</button>
                </div>
            </div>
        </div>
    `);
    $('#datepicker-manager-create-show').pickadate({
        formatSubmit: 'yyyy/mm/dd',
        hiddenName: true,
        min: new Date(),
        klass: { input: 'input' },
        onSet: function(event) {
            if (event.select) {
                showDate = this.get('select', 'yyyy/mm/dd');
                console.log("Show date set:", showDate);
                $(this.$node).removeClass('is-danger').addClass('is-success');
            }
        }
    });
    $('#timepicker-manager-create-show').pickatime({
        formatSubmit: 'HHi',
        hiddenName: true,
        interval: 15,
        min: [8, 0],
        max: [22, 0],
        klass: { input: 'input' },
        onSet: function(event) {
            if (event.select || event.highlight) {
                const selectedTime = this.get('select');
                if(selectedTime) {
                    showTime = selectedTime.hour * 100 + selectedTime.mins;
                    console.log("Show time set:", showTime);
                    $(this.$node).removeClass('is-danger').addClass('is-success');
                } else {
                    showTime = null;
                }
            }
        }
    });
    $('#manager-dynamic-2, #manager-dynamic-3, #manager-dynamic-4, #manager-dynamic-5').html('');
    $('#manager-dynamic-1').closest('.section').removeClass('is-hidden');
}

function getValidMovies() {
    console.log("Manager: Getting valid movies for date/time selection.");
    let errors = false;
    if (!showDate) {
        $('#datepicker-manager-create-show').addClass('is-danger');
        errors = true;
    } else {
        $('#datepicker-manager-create-show').removeClass('is-danger');
    }
    if (showTime === null || showTime === undefined) {
        $('#timepicker-manager-create-show').addClass('is-danger');
        errors = true;
    } else {
        $('#timepicker-manager-create-show').removeClass('is-danger');
    }
    if (errors) {
        $('#manager-dynamic-2').html(createNotification('Please select both a date and time first.', 'is-warning'));
        return;
    }
    console.log("Finding movies available on", showDate, "at", showTime);
    $('#manager-dynamic-1 input, #manager-dynamic-1 button');
    $('#manager-dynamic-1 button').addClass('is-loading');
    $('#manager-dynamic-2').html('<progress class="progress is-small is-info" max="100">15%</progress>');

    $.ajax({
        type: 'POST',
        url: '/getValidMovies',
        data: {
            'showDate': showDate
        },
        success: function(response) {
            $('#manager-dynamic-1 button').removeClass('is-loading');
            $('#manager-dynamic-2').html(response);
            $('#manager-dynamic-2 button').addClass('button is-link m-1');
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("getValidMovies AJAX error:", textStatus, errorThrown);
            $('#manager-dynamic-2').html(createNotification('Could not load available movies. Please try again.', 'is-warning'));
            $('#manager-dynamic-1 input, #manager-dynamic-1 button').prop('disabled', false);
            $('#manager-dynamic-1 button').removeClass('is-loading');
        }
    });
    $('#manager-dynamic-3, #manager-dynamic-4, #manager-dynamic-5').html('');
}

function selectShowMovie(movID, availableTypes) {
    movieID = movID;
    console.log("Manager: Selected movie", movieID, "Available types:", availableTypes);
    $('#manager-dynamic-2 button');
    let typesHtml = '<h4 class="title is-5 mt-4 mb-3 has-text-centered">Select Movie Type For Show</h4>'; 
    typesHtml += '<div class="buttons is-centered mt-3">';

    availableTypes.split(' ').forEach(function(t) {
        if (t) {
            typesHtml += `<button class="button is-success" onclick="selectShowType('${t}')">${t}</button>`;
        }
    });
    typesHtml += '</div></div>';
    $('#manager-dynamic-3').html(typesHtml);
    $('#manager-dynamic-4, #manager-dynamic-5').html('');
}

function selectShowType(t) {
    type = t;
    console.log("Manager: Selected type", type, "for movie", movieID, "on", showDate, "at", showTime);
    $('#manager-dynamic-4').html('<progress class="progress is-small is-info" max="100">15%</progress>');

    $.ajax({
        type: 'POST',
        url: '/getHallsAvailable',
        data: {
            'showDate': showDate,
            'showTime': showTime,
            'movieID': movieID
        },
        success: function(response) {
            $('#manager-dynamic-3 button');
            $('#manager-dynamic-4').html(response);
            $('#manager-dynamic-4 button').addClass('button is-primary m-1');
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("selectShowType AJAX error:", textStatus, errorThrown);
            $('#manager-dynamic-4').html(createNotification('Could not check hall availability. Please try again.', 'is-warning'));
        }
    });
    $('#manager-dynamic-5').html('');
}

function selectShowHall(hallID) {
    console.log("Manager: Selected Hall", hallID, "for scheduling show.");
    $('#manager-dynamic-5').html('<progress class="progress is-small is-info" max="100">15%</progress>');
    $('#manager-dynamic-4 button').addClass('is-loading');

    $.ajax({
        type: 'POST',
        url: '/insertShow',
        data: {
            'hallID': hallID,
            'movieType': type,
            'showDate': showDate,
            'showTime': showTime,
            'movieID': movieID
        },
        success: function(response) {
            $('#manager-dynamic-4 button').removeClass('is-loading').prop('disabled', true);
            $('#manager-dynamic-5').html(response);
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("selectShowHall AJAX error:", textStatus, errorThrown);
            $('#manager-dynamic-5').html(createNotification('Failed to schedule the show. Please try again.', 'is-danger'));
            $('#manager-dynamic-4 button').removeClass('is-loading').prop('disabled', false);
        }
    });
}

function alterPricing() {
    console.log("Manager action: Alter Pricing");
    $('#options button');
    $('#options button.is-info').removeClass('is-info').addClass('is-light');
    $('#manager-dynamic-1').html('<progress class="progress is-small is-info" max="100">15%</progress>');

    $.ajax({
        type: 'GET',
        url: '/getPriceList',
        success: function(response) {
            $('#manager-dynamic-1').html('<div class="box">' + response + '</div>');
            $('#manager-dynamic-1 .price-item').addClass('block');
            $('#manager-dynamic-1 .button').addClass('button is-link is-small ml-3');
            $('#manager-dynamic-1 table').addClass('table is-fullwidth is-striped');
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("alterPricing AJAX error:", textStatus, errorThrown);
            $('#manager-dynamic-1').html(createNotification('Could not load the current price list.', 'is-warning'));
        }
    });
    $('#manager-dynamic-2, #manager-dynamic-3, #manager-dynamic-4, #manager-dynamic-5').html('');
    $('#manager-dynamic-1').closest('.section').removeClass('is-hidden');
}

function alterPrice(mpriceID) {
    priceID = mpriceID;
    console.log("Manager: Altering price for priceID:", priceID);
    $('#manager-dynamic-1 button');
    $('#manager-dynamic-2').html(`
        <div class="box mt-4">
             <h5 class="title is-6 mb-3">Set New Price for ID ${priceID}</h5>
             <div class="field">
                <label class="label" for="new_price_input">New Price (Standard Seat Base)</label>
                <div class="control has-icons-left">
                     <input class="input" type="number" name="new_price" id="new_price_input" placeholder="Enter new base price" min="0" step="1">
                     <span class="icon is-small is-left">
                        <i class="fas fa-rupee-sign"></i> </span>
                </div>
                <p class="help">Premium seats might have a different final price based on this.</p>
            </div>
            <div class="field">
                <div class="control">
                    <button class="button is-primary" onclick="changePrice()">Change Price</button>
                </div>
            </div>
        </div>
    `);
    $('#manager-dynamic-3, #manager-dynamic-4, #manager-dynamic-5').html('');
}

function changePrice() {
    var newPrice = $('input[name="new_price"]').val();
    console.log("Manager: Setting new price", newPrice, "for priceID", priceID);
    $('#manager-dynamic-3').html('');
    $('input[name="new_price"]').removeClass('is-danger');

    if (newPrice === '' || newPrice === null || !$.isNumeric(newPrice) || parseFloat(newPrice) < 0) {
        $('input[name="new_price"]').addClass('is-danger');
        $('#manager-dynamic-3').html(createNotification('Please enter a valid, non-negative price.', 'is-warning'));
        return;
    }
    $('#manager-dynamic-2 input, #manager-dynamic-2 button');
    $('#manager-dynamic-2 button').addClass('is-loading');

    $.ajax({
        type: 'POST',
        url: '/setNewPrice',
        data: {
            'priceID': priceID,
            'newPrice': newPrice
        },
        success: function(response) {
            $('#manager-dynamic-3').html(response);
            $('#manager-dynamic-2 button').removeClass('is-loading');
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("changePrice AJAX error:", textStatus, errorThrown);
            $('#manager-dynamic-3').html(createNotification('Failed to update the price. Please try again.', 'is-danger'));
            $('#manager-dynamic-2 input, #manager-dynamic-2 button').prop('disabled', false);
            $('#manager-dynamic-2 button').removeClass('is-loading');
        }
    });
}