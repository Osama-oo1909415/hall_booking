document.addEventListener('DOMContentLoaded', () => {
    // --- STATE MANAGEMENT ---
    let currentDate = new Date();

    // --- CONFIG ---
    // Direct Cloud Function URL (fallback if rewrites don't work)
    const API_BASE_URL = 'https://api-2xaszuswfq-uc.a.run.app'; 

    // --- UI ELEMENTS ---
    const dateDisplay = document.getElementById('date-display');
    const bookingsTableContainer = document.getElementById('bookings-table-container');
    const prevDayBtn = document.getElementById('prevDayBtn');
    const nextDayBtn = document.getElementById('nextDayBtn');
    const todayBtn = document.getElementById('todayBtn');
    const bookingForm = document.getElementById('booking-form');
    const flashContainer = document.getElementById('flash-container');
    const todaysCountPill = document.getElementById('todays-count');
    const hoursBookedPill = document.getElementById('hours-booked');
    
    // --- HELPER FUNCTIONS ---
    
    const formatDate = (date) => {
        return date.toISOString().split('T')[0];
    };

    const showFlashMessage = (message, type = 'err') => {
        flashContainer.innerHTML = `<div class="flash ${type}">${message}</div>`;
        setTimeout(() => flashContainer.innerHTML = '', 5000);
    };
    
    const renderBookings = (bookings) => {
        if (!bookings || bookings.length === 0) {
            bookingsTableContainer.innerHTML = '<div class="empty">لا توجد حجوزات في هذا اليوم.</div>';
            return;
        }

        let tableHTML = `
            <table>
                <thead>
                    <tr>
                        <th>العنوان</th>
                        <th>الاسم</th>
                        <th>الوقت</th>
                        <th style="width: 120px;">إجراء</th>
                    </tr>
                </thead>
                <tbody>
        `;
        bookings.forEach(b => {
            const startTime = b.start_at.split(' ')[1];
            const endTime = b.end_at.split(' ')[1];
            tableHTML += `
                <tr>
                    <td><strong>${b.title}</strong></td>
                    <td>${b.name}</td>
                    <td><span class="tag">${startTime} - ${endTime}</span></td>
                    <td>
                        <button class="btn-ghost" data-id="${b.id}">حذف</button>
                    </td>
                </tr>
            `;
        });
        tableHTML += '</tbody></table>';
        bookingsTableContainer.innerHTML = tableHTML;
    };

    // --- API CALLS ---
    
    const fetchBookings = async (date) => {
        bookingsTableContainer.innerHTML = '<div class="empty">يتم الآن تحميل الحجوزات...</div>';
        try {
            const dateString = formatDate(date);
            const url = `${API_BASE_URL}/bookings?date=${dateString}`;
            console.log('Fetching bookings from:', url);
            
            const response = await fetch(url);
            console.log('Response status:', response.status);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: 'Network response was not ok' }));
                throw new Error(errorData.message);
            }
            const data = await response.json();
            console.log('Received data:', data);
            
            renderBookings(data.bookings);
            todaysCountPill.textContent = `إجمالي الحجوزات اليوم: ${data.todays_count}`;
            hoursBookedPill.textContent = `مجموع الساعات المحجوزة: ${data.hours_booked}`;
        } catch (error) {
            console.error('Error fetching bookings:', error);
            showFlashMessage('حدث خطأ أثناء جلب الحجوزات.');
            bookingsTableContainer.innerHTML = '<div class="empty">فشل تحميل الحجوزات.</div>';
        }
    };

    // --- INITIALIZATION AND EVENT LISTENERS ---

    const updateUI = () => {
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        dateDisplay.textContent = currentDate.toLocaleDateString('ar-QA', options);
        fetchBookings(currentDate);
        setDefaultTimes();
    };

    const setDefaultTimes = () => {
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        now.setSeconds(0);
        now.setMilliseconds(0);
        
        const startInput = document.getElementById('start_at');
        startInput.value = now.toISOString().slice(0, 16);

        const end = new Date(now.getTime() + 60 * 60 * 1000);
        const endInput = document.getElementById('end_at');
        endInput.value = end.toISOString().slice(0, 16);
    };

    prevDayBtn.addEventListener('click', () => {
        currentDate.setDate(currentDate.getDate() - 1);
        updateUI();
    });

    nextDayBtn.addEventListener('click', () => {
        currentDate.setDate(currentDate.getDate() + 1);
        updateUI();
    });
    
    todayBtn.addEventListener('click', () => {
        currentDate = new Date();
        updateUI();
    });

    bookingForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(bookingForm);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch(`${API_BASE_URL}/book`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await response.json();
            if (response.ok) {
                showFlashMessage(result.message, 'ok');
                fetchBookings(currentDate); 
                bookingForm.reset();
                setDefaultTimes();
            } else {
                showFlashMessage(result.message || 'فشل إنشاء الحجز.');
            }
        } catch (error) {
            console.error('Error creating booking:', error);
            showFlashMessage('حدث خطأ في الشبكة.');
        }
    });

    bookingsTableContainer.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-ghost') && e.target.dataset.id) {
            const bookingId = e.target.dataset.id;
            
            if (window.confirm('هل أنت متأكد من حذف هذا الحجز؟')) {
                try {
                    const response = await fetch(`${API_BASE_URL}/delete/${bookingId}`, {
                        method: 'DELETE',
                    });
                    const result = await response.json();
                     if (response.ok) {
                        showFlashMessage(result.message, 'ok');
                        fetchBookings(currentDate); // Refresh
                    } else {
                        showFlashMessage(result.message || 'فشل حذف الحجز.');
                    }
                } catch(error) {
                    console.error('Error deleting booking:', error);
                    showFlashMessage('حدث خطأ في الشبكة.');
                }
            }
        }
    });
    
    document.getElementById('footer-year').textContent = new Date().getFullYear();
    updateUI();
});

