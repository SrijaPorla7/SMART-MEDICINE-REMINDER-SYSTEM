// State management
let activeUserId = "1";
let complianceChart = null;
let currentSchedules = [];
let nextReminderInterval = null;

// On load
document.addEventListener("DOMContentLoaded", () => {
    // 1. Set current date default for start date input in form
    const todayStr = new Date().toISOString().split('T')[0];
    document.getElementById("med-start").value = todayStr;

    // 2. Initialize live clock
    startLiveClock();

    // 3. Load initial data
    loadAllUserData();
    loadDoctorPortal();

    // 4. Handle email redirect toasts
    checkUrlParameters();
});

// Live Clock in Header
function startLiveClock() {
    setInterval(() => {
        const now = new Date();
        document.getElementById("current-time").innerText = now.toLocaleTimeString();
    }, 1000);
}

// Check if redirected from email landing page click
function checkUrlParameters() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("action") === "marked_taken") {
        const medName = params.get("med_name") || "Medication";
        showToast(`✅ Successfully marked ${decodeURIComponent(medName)} as taken!`, "success");
        // Clear url parameters to avoid repeat alerts on refresh
        window.history.replaceState({}, document.title, "/");
    }
}

// Load Tab views
function switchTab(tabId) {
    // Nav items active state
    document.querySelectorAll(".nav-item").forEach(item => {
        item.classList.remove("active");
    });
    const activeNav = document.querySelector(`.nav-item[href="#${tabId}"]`);
    if (activeNav) activeNav.classList.add("active");

    // Panels visibility
    document.querySelectorAll(".tab-pane").forEach(pane => {
        pane.classList.remove("active");
    });
    document.getElementById(`tab-${tabId}`).classList.add("active");

    // Page title headers
    const titleEl = document.getElementById("page-title");
    const subtitleEl = document.getElementById("page-subtitle");
    if (tabId === "dashboard") {
        titleEl.innerText = "Medication Dashboard";
        subtitleEl.innerText = "Real-time medication tracker and alerts";
        loadAllUserData();
    } else if (tabId === "schedule") {
        titleEl.innerText = "Add Schedule";
        subtitleEl.innerText = "Add a new medication and reminder details";
    } else if (tabId === "adherence") {
        titleEl.innerText = "Compliance Reports";
        subtitleEl.innerText = "Historical charts and adherence rates";
        loadAllUserData();
    } else if (tabId === "doctor") {
        titleEl.innerText = "Doctor Portal";
        subtitleEl.innerText = "Monitor adherence metrics of all registered patients";
        loadDoctorPortal();
    }
}

// Trigger User Switcher
function onUserChange() {
    const select = document.getElementById("user-select");
    activeUserId = select.value;
    showToast(`Switched active patient to ${select.options[select.selectedIndex].text}`, "success");
    loadAllUserData();
}

// Combined loader for user-specific data
function loadAllUserData() {
    fetchSchedules();
    fetchAdherenceReport();
    fetchAIPredictions();
}

// 1. Fetch patient medicine schedule list
async function fetchSchedules() {
    const medContainer = document.getElementById("med-list");
    try {
        const res = await fetch(`/medicines/${activeUserId}`);
        const data = await res.json();
        
        if (!data.success || !data.data) {
            medContainer.innerHTML = `<div class="empty-state"><i class="fa-solid fa-circle-exclamation"></i><p>Could not fetch schedules.</p></div>`;
            return;
        }

        currentSchedules = data.data.filter(s => s.is_active);
        document.getElementById("checklist-count").innerText = `${currentSchedules.length} Doses`;

        // We will fetch their today's logs to match checked/pending state
        const reportRes = await fetch(`/adherence-report/${activeUserId}`);
        const reportData = await reportRes.json();
        const logs = reportData.success ? reportData.data.recent_logs : [];

        renderTodayScheduleList(currentSchedules, logs);
        startCountdownTimer(currentSchedules);

    } catch (err) {
        console.error(err);
        medContainer.innerHTML = `<div class="empty-state"><i class="fa-solid fa-circle-exclamation"></i><p>Error connecting to API.</p></div>`;
    }
}

// Helper to determine status and render elements
function renderTodayScheduleList(schedules, logs) {
    const medContainer = document.getElementById("med-list");
    if (schedules.length === 0) {
        medContainer.innerHTML = `<div class="empty-state"><i class="fa-solid fa-circle-check"></i><p>All clear! No active medicine reminders scheduled.</p></div>`;
        return;
    }

    const todayStr = new Date().toISOString().split('T')[0];
    let html = '';

    schedules.forEach(sched => {
        // Find if this dose was logged for today
        const scheduledTimeStr = sched.reminder_time; // HH:MM:SS
        const scheduledDatetimeTarget = `${todayStr}T${scheduledTimeStr}`;
        
        // Find log matches (handling different date separators)
        const logMatch = logs.find(log => {
            const cleanLogDt = log.scheduled_datetime.replace(' ', 'T');
            return log.schedule_id === sched.schedule_id && cleanLogDt.startsWith(todayStr);
        });

        let status = 'Pending';
        let badgeClass = 'badge-pending';
        let actionButtonHtml = '';

        if (logMatch) {
            status = logMatch.status;
            if (status === 'Taken') badgeClass = 'badge-taken';
            else if (status === 'Missed') badgeClass = 'badge-missed';
            else if (status === 'Skipped') badgeClass = 'badge-skipped';
            else if (status === 'Delayed') badgeClass = 'badge-taken'; // count as taken
        } else {
            // If not logged yet, check if it is already past 15 mins (deemed missed on UI)
            const now = new Date();
            const schedTime = new Date(`${todayStr}T${scheduledTimeStr}`);
            const diffMins = (now - schedTime) / 60000;

            if (diffMins > 15) {
                status = 'Missed';
                badgeClass = 'badge-missed';
            }
        }

        // Show Take button only if status is not Taken / Delayed / Skipped
        if (status !== 'Taken' && status !== 'Delayed' && status !== 'Skipped') {
            actionButtonHtml = `
                <button class="btn btn-success-outline btn-sm" onclick="markAsTaken(${sched.schedule_id}, '${todayStr} ${scheduledTimeStr}')">
                    <i class="fa-solid fa-check"></i> Mark Taken
                </button>
            `;
        } else {
            actionButtonHtml = `<span class="badge ${badgeClass}"><i class="fa-solid fa-circle-check"></i> Completed</span>`;
        }

        const iconClass = getFormIcon(sched.form);

        html += `
            <div class="med-item">
                <div class="med-item-left">
                    <div class="med-icon-box">
                        <i class="${iconClass}"></i>
                    </div>
                    <div class="med-details">
                        <h4>${sched.medicine_name}</h4>
                        <div class="med-meta">
                            <span><i class="fa-solid fa-capsules"></i> ${sched.dosage}</span>
                            <span class="divider">|</span>
                            <span><i class="fa-solid fa-clock"></i> ${formatTime12h(sched.reminder_time)}</span>
                            ${sched.special_instructions ? `<span class="divider">|</span> <span class="instructions"><i class="fa-solid fa-info-circle"></i> ${sched.special_instructions}</span>` : ''}
                        </div>
                    </div>
                </div>
                <div class="med-item-right">
                    <span class="badge ${badgeClass}">${status}</span>
                    ${actionButtonHtml}
                </div>
            </div>
        `;
    });

    medContainer.innerHTML = html;
}

// 2. Mark dose as taken
async function markAsTaken(scheduleId, scheduledDatetime) {
    try {
        const res = await fetch('/mark-taken', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                schedule_id: scheduleId,
                scheduled_datetime: scheduledDatetime,
                status: 'Taken'
            })
        });
        const data = await res.json();
        
        if (data.success) {
            showToast("Medication dose logged successfully!", "success");
            loadAllUserData();
            loadDoctorPortal(); // Update doctor compliance ratios
        } else {
            showToast(`Error logging dose: ${data.message}`, "error");
        }
    } catch (err) {
        console.error(err);
        showToast("Network error logging medication dose.", "error");
    }
}

// 3. Countdown timer calculations
function startCountdownTimer(schedules) {
    if (nextReminderInterval) clearInterval(nextReminderInterval);
    if (schedules.length === 0) {
        document.getElementById("countdown-timer").innerText = "--:--:--";
        document.getElementById("next-med-details").innerText = "No active schedules";
        return;
    }

    const timerEl = document.getElementById("countdown-timer");
    const detailsEl = document.getElementById("next-med-details");

    const updateTimer = () => {
        const now = new Date();
        const todayStr = now.toISOString().split('T')[0];
        
        let nextDose = null;
        let minDiff = Infinity;

        schedules.forEach(sched => {
            const timeParts = sched.reminder_time.split(":");
            const schedTimeToday = new Date();
            schedTimeToday.setHours(parseInt(timeParts[0]), parseInt(timeParts[1]), parseInt(timeParts[2] || "0"), 0);

            let diff = schedTimeToday - now;
            // If the time has passed for today, it's due tomorrow
            if (diff < 0) {
                const schedTimeTomorrow = new Date(schedTimeToday);
                schedTimeTomorrow.setDate(schedTimeTomorrow.getDate() + 1);
                diff = schedTimeTomorrow - now;
            }

            if (diff < minDiff) {
                minDiff = diff;
                nextDose = {
                    sched: sched,
                    targetTime: new Date(now.getTime() + diff)
                };
            }
        });

        if (!nextDose) return;

        // Calculate hours, minutes, seconds remaining
        const hours = Math.floor(minDiff / 3600000);
        const mins = Math.floor((minDiff % 3600000) / 60000);
        const secs = Math.floor((minDiff % 60000) / 1000);

        timerEl.innerText = `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        detailsEl.innerText = `${nextDose.sched.medicine_name} (${nextDose.sched.dosage}) at ${formatTime12h(nextDose.sched.reminder_time)}`;
    };

    updateTimer();
    nextReminderInterval = setInterval(updateTimer, 1000);
}

// 4. Fetch AI High-risk predictions
async function fetchAIPredictions() {
    try {
        const res = await fetch(`/prediction/${activeUserId}`);
        const data = await res.json();
        
        const riskWindowEl = document.getElementById("ai-risk-window");
        const riskDescEl = document.getElementById("ai-risk-desc");

        if (data.success && data.data) {
            riskWindowEl.innerText = data.data.high_risk_window;
            riskDescEl.innerText = data.data.message;
        } else {
            riskWindowEl.innerText = "No Pattern";
            riskDescEl.innerText = "Insufficent compliance data";
        }
    } catch (err) {
        console.error("Failed to fetch predictions", err);
    }
}

// 5. Fetch Adherence Report & Render Chart.js
async function fetchAdherenceReport() {
    try {
        const res = await fetch(`/adherence-report/${activeUserId}`);
        const data = await res.json();

        if (!data.success || !data.data) return;

        const summary = data.data.adherence_summary;
        document.getElementById("adherence-rate").innerText = `${summary.adherence_rate_percentage}%`;

        // Render recent log table
        const tableBody = document.getElementById("logs-table-body");
        if (data.data.recent_logs.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No historical compliance logs found.</td></tr>`;
        } else {
            tableBody.innerHTML = data.data.recent_logs.map(log => {
                const schedTime = formatDatetimeReadable(log.scheduled_datetime);
                const actualTime = log.taken_datetime ? formatDatetimeReadable(log.taken_datetime) : '--:--';
                let badgeClass = 'badge-pending';
                if (log.status === 'Taken') badgeClass = 'badge-taken';
                else if (log.status === 'Missed') badgeClass = 'badge-missed';
                else if (log.status === 'Skipped') badgeClass = 'badge-skipped';
                
                return `
                    <tr>
                        <td><strong>${log.medicine_name}</strong></td>
                        <td>${log.dosage}</td>
                        <td>${schedTime}</td>
                        <td>${actualTime}</td>
                        <td><span class="badge ${badgeClass}">${log.status}</span></td>
                        <td><span class="text-muted">${log.notes || '-'}</span></td>
                    </tr>
                `;
            }).join('');
        }

        // Render Chart.js data
        renderChart(summary.details);

    } catch (err) {
        console.error("Error fetching compliance reports", err);
    }
}

// Chart.js render logic
function renderChart(details) {
    const ctx = document.getElementById('complianceChart').getContext('2d');
    
    // Destroy previous instance to avoid rendering overlaps
    if (complianceChart) {
        complianceChart.destroy();
    }

    complianceChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Taken Doses', 'Delayed Doses', 'Skipped Doses', 'Missed Doses'],
            datasets: [{
                label: 'Doses Checked',
                data: [details.Taken, details.Delayed || 0, details.Skipped, details.Missed],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.45)', // Taken -> Emerald
                    'rgba(99, 102, 241, 0.45)',  // Delayed -> Indigo
                    'rgba(148, 163, 184, 0.45)', // Skipped -> Gray
                    'rgba(239, 68, 68, 0.45)'    // Missed -> Rose
                ],
                borderColor: [
                    '#10B981',
                    '#6366F1',
                    '#94A3B8',
                    '#EF4444'
                ],
                borderWidth: 2,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: '#94A3B8',
                        stepSize: 1
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    }
                },
                x: {
                    ticks: {
                        color: '#94A3B8'
                    },
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// 6. Submit Schedule Form
async function submitMedicineForm(event) {
    event.preventDefault();
    
    const medPayload = {
        patient_id: parseInt(activeUserId),
        name: document.getElementById("med-name").value,
        form: document.getElementById("med-form").value,
        strength: document.getElementById("med-strength").value,
        dosage: document.getElementById("med-dosage").value,
        frequency: document.getElementById("med-frequency").value,
        reminder_time: document.getElementById("med-time").value + ":00",
        start_date: document.getElementById("med-start").value,
        end_date: document.getElementById("med-end").value || null,
        special_instructions: document.getElementById("med-instructions").value,
        manufacturer: document.getElementById("med-manufacturer").value || null
    };

    try {
        const res = await fetch('/add-medicine', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(medPayload)
        });
        const data = await res.json();

        if (data.success) {
            showToast("Medicine scheduled successfully!", "success");
            document.getElementById("add-medicine-form").reset();
            // Reset dates defaults
            document.getElementById("med-start").value = new Date().toISOString().split('T')[0];
            
            // Switch back to dashboard to see results
            switchTab('dashboard');
        } else {
            showToast(`Failed to add schedule: ${data.message}`, "error");
        }

    } catch (err) {
        console.error(err);
        showToast("Error connecting to server to add schedule.", "error");
    }
}

// 7. Load Doctor Portal Patient list
async function loadDoctorPortal() {
    const tableBody = document.getElementById("patients-table-body");
    if (!tableBody) return;
    try {
        const res = await fetch('/doctor/patients');
        const data = await res.json();

        if (!data.success || !data.data) {
            tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">Failed to load patients list.</td></tr>`;
            return;
        }

        renderPatientsList(data.data);

    } catch (err) {
        console.error(err);
        tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Server connection error.</td></tr>`;
    }
}

function renderPatientsList(patients) {
    const tableBody = document.getElementById("patients-table-body");
    if (patients.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No patients registered.</td></tr>`;
        return;
    }

    tableBody.innerHTML = patients.map(p => {
        const compliance = p.adherence_percentage;
        let badgeClass = 'badge-missed';
        if (compliance >= 85) badgeClass = 'badge-taken';
        else if (compliance >= 60) badgeClass = 'badge-pending';

        return `
            <tr>
                <td>P-${p.patient_id.toString().padStart(3, '0')}</td>
                <td><strong>${p.name}</strong></td>
                <td>${p.email}</td>
                <td>${p.phone}</td>
                <td><span class="text-secondary">${p.medicines}</span></td>
                <td><strong>${compliance}%</strong></td>
                <td><span class="badge ${badgeClass}">${compliance >= 85 ? 'Excellent' : compliance >= 60 ? 'Borderline' : 'At Risk'}</span></td>
            </tr>
        `;
    }).join('');
}

// Client Side Search Filter in Doctor Portal
function filterPatients() {
    const query = document.getElementById("patient-search").value.toLowerCase();
    const rows = document.querySelectorAll("#patients-table-body tr");

    rows.forEach(row => {
        const patientName = row.querySelector("td:nth-child(2)").innerText.toLowerCase();
        if (patientName.includes(query)) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    });
}

// Form Icon Mapper
function getFormIcon(form) {
    switch (form) {
        case 'Tablet': return 'fa-solid fa-pills';
        case 'Capsule': return 'fa-solid fa-capsules';
        case 'Syrup': return 'fa-solid fa-prescription-bottle';
        case 'Injection': return 'fa-solid fa-syringe';
        case 'Inhaler': return 'fa-solid fa-wind';
        case 'Drops': return 'fa-solid fa-eye-dropper';
        default: return 'fa-solid fa-prescription-bottle-medical';
    }
}

// Toast Notification Pop-up
function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    const iconClass = type === "success" ? "fa-circle-check" : "fa-circle-exclamation";
    toast.innerHTML = `
        <i class="fa-solid ${iconClass}"></i>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    // Auto fadeout
    setTimeout(() => {
        toast.style.animation = "fadeIn 0.3s ease reverse forwards";
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 4000);
}

// Time Formatting Helpers
function formatTime12h(timeString) {
    if (!timeString) return '';
    const parts = timeString.split(':');
    let hours = parseInt(parts[0]);
    const minutes = parts[1];
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12; // 0 hour represents 12 AM
    return `${hours}:${minutes} ${ampm}`;
}

function formatDatetimeReadable(dtStr) {
    if (!dtStr) return '';
    const date = new Date(dtStr);
    const datePart = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    const timePart = date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    return `${datePart}, ${timePart}`;
}
