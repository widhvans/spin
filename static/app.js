const TelegramWebApp = window.Telegram.WebApp;
TelegramWebApp.ready();

const user = TelegramWebApp.initDataUnsafe.user;
const userId = user ? user.id : null;
const username = user ? (user.username || user.first_name) : "Guest";

const backendUrl = window.location.origin; // Use the same domain as the Mini App

// Initialize Mini App
async function init() {
    if (!userId) {
        document.getElementById("user-info").innerHTML = "<p>Error: User not authenticated.</p>";
        return;
    }

    const userData = await fetchUserData(userId);
    if (userData.error) {
        document.getElementById("user-info").innerHTML = `<p>Error: ${userData.error}</p>`;
        return;
    }
    updateUI(userData);
}

// Fetch user data
async function fetchUserData(userId) {
    try {
        const response = await fetch(`${backendUrl}/api/user/${userId}`);
        return await response.json();
    } catch (error) {
        return { error: "Failed to fetch user data" };
    }
}

// Perform spin
async function performSpin(userId) {
    try {
        const response = await fetch(`${backendUrl}/api/spin/${userId}`, { method: 'POST' });
        return await response.json();
    } catch (error) {
        return { error: "Failed to perform spin" };
    }
}

// Request withdrawal
async function requestWithdrawal(userId, upiDetails) {
    try {
        const response = await fetch(`${backendUrl}/api/withdraw/${userId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ upi_details: upiDetails })
        });
        return await response.json();
    } catch (error) {
        return { error: "Failed to request withdrawal" };
    }
}

// Update UI with user data
function updateUI(userData) {
    const { balance, spins_left, referrals, referral_code, referral_earnings } = userData;
    const referralLink = `https://t.me/SpinAndWinBot?start=${referral_code}`; // Replace with your bot username

    document.getElementById("user-info").innerHTML = `
        <p class="text-lg font-semibold">Welcome, ${username}!</p>
        <p>💰 Balance: ₹${balance}</p>
        <p>🎰 Spins Left: ${spins_left}</p>
    `;

    document.getElementById("dashboard-content").innerHTML = `
        <p>💰 Balance: ₹${balance}</p>
        <p>🎰 Spins Left: ${spins_left}</p>
        <p>👥 Referrals: ${referrals.length}/15</p>
        <p>🎁 Referral Earnings: ₹${referral_earnings}</p>
        <p>${referrals.length >= 15 && balance >= 100 ? "✅ Ready to withdraw!" : "🔒 Need 15 referrals and ₹100 to withdraw"}</p>
    `;

    document.getElementById("referral-link").innerHTML = `
        <p>Share your referral link:</p>
        <p class="break-all">${referralLink}</p>
    `;

    document.getElementById("withdrawal-status").innerHTML = `
        <p>${referrals.length >= 15 && balance >= 100 ? "✅ Eligible for withdrawal!" : "🔒 Need 15 referrals and ₹100 to withdraw"}</p>
    `;
}

// Spin button handler
document.getElementById("spin-button").addEventListener("click", async () => {
    const userData = await fetchUserData(userId);
    if (userData.error || userData.spins_left <= 0) {
        document.getElementById("spin-result").textContent = "No spins left! Invite friends to earn more.";
        return;
    }

    document.getElementById("spin-button").disabled = true;
    const wheel = document.getElementById("wheel");
    wheel.classList.add("animate-spin");
    setTimeout(async () => {
        wheel.classList.remove("animate-spin");
        const result = await performSpin(userId);
        if (result.error) {
            document.getElementById("spin-result").textContent = result.error;
        } else {
            document.getElementById("spin-result").textContent = `You won ₹${result.reward}!`;
            const newUserData = await fetchUserData(userId);
            updateUI(newUserData);
        }
        document.getElementById("spin-button").disabled = false;
    }, 2000);
});

// Copy referral link
document.getElementById("copy-referral").addEventListener("click", async () => {
    const userData = await fetchUserData(userId);
    const referralLink = `https://t.me/SpinAndWinBot?start=${userData.referral_code}`; // Replace with your bot username
    navigator.clipboard.writeText(referralLink);
    alert("Referral link copied!");
});

// Withdrawal button handler
document.getElementById("withdraw-button").addEventListener("click", async () => {
    const userData = await fetchUserData(userId);
    if (userData.referrals.length < 15 || userData.balance < 100) {
        alert("You need 15 referrals and ₹100 balance to withdraw!");
        return;
    }

    const upiDetails = prompt("Enter your UPI ID and Name (e.g., name@upi):");
    if (upiDetails) {
        const result = await requestWithdrawal(userId, upiDetails);
        alert(result.message || result.error);
    }
});

// Animation for spin
const style = document.createElement("style");
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    .animate-spin {
        animation: spin 2s linear;
    }
`;
document.head.appendChild(style);

// Initialize app
init();
