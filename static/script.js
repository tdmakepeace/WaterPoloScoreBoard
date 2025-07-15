        function playSound() {
            var audio = new Audio('/static/airhorn.mp3');
            audio.play();
        }
        function playbell() {
            var audio = new Audio('/static/bell-ring.mp3');
            audio.play();
        }
        function startCountdown() {
            $.ajax({
                url: '/start_countdown',
                success: function(response) {
                    updateCountdown();
                }
            });
        }

       //
       document.addEventListener('DOMContentLoaded', (event) => {
            document.addEventListener('keydown', function(event) {
                 if (event.key === 'n') {
                    event.preventDefault();
                    pauseCountdown()
                }
                // shared
                else if (event.key === 'c') {
                    event.preventDefault();
                    window.location.href = '/major';
                }
                else if (event.key === 'v') {
                    event.preventDefault();
                    window.location.href = '/goal';
                    // Perform another action here
                }
                else if (event.key === 'b') {
                    event.preventDefault();
                    window.location.href = '/penalty';
                }

                // Away
                else if (event.key === 't') {
                    event.preventDefault();
                    window.location.href = '/awaytimeout';
                }
                else if (event.key === 'g') {
                    event.preventDefault();
                    window.location.href = '/awaycard';
                }
                 //Home
                else if ( event.key === 'r') {
                     event.preventDefault();
                    window.location.href = '/hometimeout';
                }
                else if (event.key === 'f') {
                    event.preventDefault();
                    window.location.href = '/homecard';
                }
                else if (event.key === 'x') {
                    event.preventDefault();
                    window.location.href = '/clear';
                }
            });
        });

        function pauseCountdown() {
            $.ajax({
                url: '/pause_countdown',
                success: function(response) {
                    updateCountdown();
                }
            });
        }
        function resumeCountdown() {
            $.ajax({
                url: '/resume_countdown',
                success: function(response) {
                    updateCountdown();
                }
            });
        }

        function stopCountdown() {
            $.ajax({
                url: '/stop_countdown',
                success: function(response) {
                    updateCountdown();
                }
            });
        }

        function updateCountdown() {
            $.ajax({
                url: '/get_countdown_status',
                success: function (response) {
                    let countdownElement = document.getElementById('countdown');
                    let shotdownElement = document.getElementById('shotdown');
                    let timeLeft = response.elapsed_time;
                    let shotLeft = response.elapsed_shot;
                    if (response.countdown_running) {
                        let minutes = Math.floor(timeLeft / 60);
                        let seconds = Math.floor(timeLeft % 60);
                        let shotseconds = Math.floor(shotLeft % 60);
                        countdownElement.innerHTML = '<br> ' + minutes + ':' + seconds.toString().padStart(2, '0') + '';
                        shotdownElement.innerHTML = '<br> ' + shotseconds.toString().padStart(2, '0') + '';
                        // countdownElement.innerHTML = 'Remaining Time: ' + seconds.toString().padStart(2, '0') + 's';
                        var quarter = {{ quarter }}
                        if (quarter < 4) {
                            if (timeLeft > 1) {
                                if (shotLeft < 1) {
                                    playSound();
                                    playSound();
                                    reset30();
                                }
                                setTimeout(updateCountdown, 1000);

                            } else {
                                playSound()
                                setTimeout(() => {
                                    window.location.href = "/callinterval";
                                }, 2000);

                            }
                        } else {
                            if (timeLeft > 61) {
                                if (shotLeft < 1) {
                                    playSound();
                                    playSound();
                                    reset30();
                                }
                                setTimeout(updateCountdown, 1000);
                            } else if (timeLeft = 60) {
                                playbell();
                                // if shotLeft = 0 {
                                //     playSound();
                                //     possession()
                                // }
                                setTimeout(updateCountdown, 1000);
                            } else if (timeLeft > 1) {
                                 if (shotLeft < 1) {
                                    playSound();
                                    playSound();
                                    reset30();
                                }
                                setTimeout(updateCountdown, 1000);

                            } else {
                                playSound();
                                setTimeout(() => {
                                    window.location.href = "/callinterval";
                                }, 2000);
                            }
                        }



                        // if  (timeLeft > 1) {
                        //     setTimeout(updateCountdown, 1000);
                        // } else {
                        //     playSound()
                        //     setTimeout(() => {
                        //         window.location.href = "/callinterval";
                        //     }, 2000);
                        //
                        // }
                    } else {
                        // countdownElement.innerHTML = '<br>Paused';
                        let timeLeft = response.elapsed_time;
                        let shotLeft = response.elapsed_shot;
                        let minutes = Math.floor(timeLeft / 60);
                        let seconds = Math.floor(timeLeft % 60);
                        let shotseconds = Math.floor(shotLeft % 60);
                        countdownElement.innerHTML = '<br> ' + minutes + ':' + seconds.toString().padStart(2, '0') + '';
                        shotdownElement.innerHTML = '<br> ' + shotseconds.toString().padStart(2, '0') + '';
                    }
                }
            });
        }


        function reset20() {
            $.ajax({
                url: '/reset20',
                success: function(response) {
                    updateCountdown();
                }
            });
        }

        function possession() {
            $.ajax({
                url: '/possession',
                success: function(response) {
                    updateCountdown();
                }
            });
        }

        function reset30() {
            $.ajax({
                url: '/reset30',
                success: function(response) {
                    updateCountdown();
                }
            });
        }

        function addmin() {
            $.ajax({
                url: '/addmin',
                success: function(response) {
                    updateCountdown();
                }
            });
        }
        function minmin() {
            $.ajax({
                url: '/minmin',
                success: function(response) {
                    updateCountdown();
                }
            });
        }
                function addsec() {
            $.ajax({
                url: '/addsec',
                success: function(response) {
                    updateCountdown();
                }
            });
        }
                function minsec() {
            $.ajax({
                url: '/minsec',
                success: function(response) {
                    updateCountdown();
                }
            });
        }
        // function homegoal() {
        //     window.open('/homegoal', 'Popup', 'width=600,height=400');
        //     // Initial update of countdown display
        // }
        updateCountdown();
