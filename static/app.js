document.addEventListener('DOMContentLoaded', () => {
    
    // Set default check-in date to today
    const checkinInput = document.getElementById('checkin');
    if (checkinInput) {
        const today = new Date().toISOString().split('T')[0];
        checkinInput.value = today;
    }
    const navItems = document.querySelectorAll('.nav li');
    const views = document.querySelectorAll('.view');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            // Remove active from all
            navItems.forEach(n => n.classList.remove('active'));
            views.forEach(v => v.classList.remove('active'));

            // Add active to clicked
            item.classList.add('active');
            const targetId = item.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');
        });
    });

    // Prediction Form Submit
    const form = document.getElementById('predict-form');
    const overlay = document.getElementById('loading-overlay');
    const initState = document.getElementById('initial-state');
    const resultPanel = document.getElementById('prediction-result');

    // State
    let currentPrediction = null;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // UI Loading
        initState.classList.add('hidden');
        resultPanel.classList.add('hidden');
        overlay.classList.remove('hidden');

        // Gather Data
        const payload = {
            ulke: document.getElementById('ulke').value,
            yas: document.getElementById('yas').value,
            cocuk: document.getElementById('cocuk').value,
            gece: document.getElementById('gece').value,
            otel: document.getElementById('otel').value,
            ilce: document.getElementById('ilce').value,
            checkin: document.getElementById('checkin').value
        };

        try {
            const res = await fetch('/api/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await res.json();

            if (result.success) {
                window.currentPrediction = result.data;
                populateResult(result.data);
                
                // Show result with slight delay for dramatic effect
                setTimeout(() => {
                    overlay.classList.add('hidden');
                    resultPanel.classList.remove('hidden');
                    animateCircle(result.data.kabul_ihtimali);
                }, 600);
            } else {
                alert("Hata: " + result.error);
                overlay.classList.add('hidden');
                initState.classList.remove('hidden');
            }
        } catch (error) {
            console.error(error);
            overlay.classList.add('hidden');
            initState.classList.remove('hidden');
        }
    });

    // XAI Charts
    let decayChartInstance = null;
    let budgetChartInstance = null;
    let harcamaPieChartInstance = null;

    function populateResult(data) {
        document.getElementById('res-tour').textContent = data.onerilecek_tur.replace('_', ' ');
        document.getElementById('res-prob').textContent = `%${data.kabul_ihtimali}`;
        document.getElementById('res-usd').textContent = `$${data.tahmini_butce_usd}`;
        document.getElementById('res-bant').textContent = data.butce_bandi;
        document.getElementById('res-gun').textContent = `Gün ${data.optimal_push_gunu}`;
        document.getElementById('res-saat').textContent = data.push_saati;
        document.getElementById('res-yas').textContent = data.yas_grubu;
        document.getElementById('res-csi').textContent = `${data.memnuniyet_csi} / 10`;

        if (data.harcama_profili) {
            renderHarcamaPieChart(data.harcama_profili);
        }

        // Render XAI Charts
        if(data.xai_proof) {
            renderDecayChart(data.xai_proof.decay_curve);
            renderBudgetChart(data.xai_proof.ulke_yas_median, data.tahmini_butce_usd, data.ulke);
            
            // Paket Olasılıkları
            const pktList = document.getElementById('paket-listesi');
            if (pktList && data.xai_proof.paket_olasiliklari) {
                pktList.innerHTML = '';
                data.xai_proof.paket_olasiliklari.forEach(p => {
                    pktList.innerHTML += `<div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.05); padding:8px 12px; border-radius:6px;">
                        <span style="font-size:13px; color:#f8fafc;">${p.paket.replace('_', ' ')}</span>
                        <span style="font-size:13px; font-weight:bold; color:${p.olasilik > 50 ? '#10b981' : '#f59e0b'};">%${p.olasilik}</span>
                    </div>`;
                });
            }
            
            // Gün Olasılıkları
            const gunList = document.getElementById('gun-listesi');
            if (gunList && data.xai_proof.gun_olasiliklari) {
                gunList.innerHTML = '';
                data.xai_proof.gun_olasiliklari.forEach(g => {
                    gunList.innerHTML += `<div style="min-width:70px; text-align:center; background:rgba(255,255,255,0.05); padding:10px; border-radius:8px; border:1px solid rgba(255,255,255,0.1);">
                        <div style="font-size:11px; color:#94a3b8; margin-bottom:4px;">${g.gun}. Gün</div>
                        <div style="font-size:14px; font-weight:bold; color:${g.olasilik > 40 ? '#3b82f6' : '#ef4444'};">%${g.olasilik}</div>
                    </div>`;
                });
            }
        }
    }

    function renderDecayChart(decayCurve) {
        const ctx = document.getElementById('decayChart').getContext('2d');
        if(decayChartInstance) decayChartInstance.destroy();
        
        decayChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['1. Gün','2. Gün','3. Gün','4. Gün','5. Gün','6. Gün','7. Gün','10. Gün','14. Gün'],
                datasets: [{
                    label: 'Memnuniyet',
                    data: [decayCurve[0], decayCurve[1], decayCurve[2], decayCurve[3], decayCurve[4], decayCurve[5], decayCurve[6], decayCurve[9], decayCurve[13]],
                    borderColor: '#f59e0b',
                    tension: 0.3,
                    fill: true,
                    backgroundColor: 'rgba(245, 158, 11, 0.1)'
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: { min: 4, max: 10, grid: { color: 'rgba(255,255,255,0.05)' } },
                    x: { grid: { color: 'rgba(255,255,255,0.05)' } }
                }
            }
        });
    }

    function renderBudgetChart(median, predicted, ulke) {
        const ctx = document.getElementById('budgetChart').getContext('2d');
        if(budgetChartInstance) budgetChartInstance.destroy();

        budgetChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [`${ulke} Medyan`, 'Bu Turist (GBM)'],
                datasets: [{
                    data: [median, predicted],
                    backgroundColor: ['rgba(148, 163, 184, 0.5)', '#10b981'],
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    function renderHarcamaPieChart(harcama) {
        const ctx = document.getElementById('harcamaPieChart').getContext('2d');
        if(harcamaPieChartInstance) harcamaPieChartInstance.destroy();

        const dataValues = [harcama.gastronomi_usd, harcama.alisveris_usd, harcama.kultur_usd, harcama.saglik_usd];
        const total = dataValues.reduce((a, b) => a + b, 0);
        
        // If total is 0 to avoid division by zero
        if(total === 0) return;

        harcamaPieChartInstance = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['Gastronomi', 'Alışveriş', 'Kültür', 'Sağlık/Spa'],
                datasets: [{
                    data: dataValues,
                    backgroundColor: [
                        '#f59e0b', // amber
                        '#3b82f6', // blue
                        '#8b5cf6', // purple
                        '#10b981'  // green
                    ],
                    borderColor: 'rgba(0,0,0,0.1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: '#cbd5e1',
                            font: { size: 11 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const value = context.raw;
                                const percentage = Math.round((value / total) * 100);
                                return ` ${context.label}: %${percentage}`;
                            }
                        }
                    }
                }
            }
        });
    }

    function animateCircle(percentage) {
        const circle = document.getElementById('prob-circle');
        circle.style.strokeDasharray = `${percentage}, 100`;
        
        // Color based on prob
        if (percentage >= 70) circle.style.stroke = '#10b981'; // Green
        else if (percentage >= 50) circle.style.stroke = '#f59e0b'; // Yellow
        else circle.style.stroke = '#ef4444'; // Red
    }

    // Load Logs initially
    fetchLogs();
    setInterval(fetchLogs, 5000); // Poll every 5s
});

// Feedback Logic (Global scope)
async function sendFeedback(sonuc, detay) {
    if (!window.currentPrediction) return;

    const payload = {
        ulke_kodu: window.currentPrediction.ulke_kodu,
        onerilen_tur: window.currentPrediction.onerilecek_tur,
        sonuc: sonuc,
        detay: detay
    };

    try {
        const res = await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.success) {
            showToast(`Bayes Modeli Güncellendi! Yeni Olasılık: %${result.yeni_ihtimal}`);
            fetchLogs(); // Reload logs instantly
        }
    } catch (e) {
        console.error(e);
    }
}

function fetchLogs() {
    fetch('/api/logs')
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('mini-logs');
            container.innerHTML = data.logs.map(log => `<div style="margin-bottom:4px; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:4px;">${log}</div>`).join('');
        });
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Attach to window so sendFeedback can access currentPrediction
window.currentPrediction = null;
const originalPopulate = window.populateResult;
