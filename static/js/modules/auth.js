/**
 * HackForge Auth Module
 * Pure JavaScript SPA Authentication Layer
 */

const API_BASE = "/api/auth";

// =========================
// STATE
// =========================

let currentUser = null;

// =========================
// HELPERS
// =========================

async function apiRequest(url, method = "GET", data = null) {
    const options = {
        method,
        headers: {
            "Content-Type": "application/json"
        },
        credentials: "include" // IMPORTANT for cookie auth
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    const res = await fetch(API_BASE + url, options);
    const json = await res.json();

    if (!res.ok) {
        throw new Error(json.message || "Request failed");
    }

    return json;
}

// =========================
// TOAST (optional hook)
// =========================

function notify(message, type = "info") {
    if (window.showToast) {
        window.showToast(message, type);
    } else {
        console.log(`[${type}] ${message}`);
    }
}

// =========================
// AUTH STATE
// =========================

export function getUser() {
    return currentUser;
}

export async function fetchMe() {
    try {
        const res = await apiRequest("/me");
        currentUser = res.data.user;
        return currentUser;
    } catch (err) {
        currentUser = null;
        return null;
    }
}

// =========================
// SIGNUP FLOW
// =========================

export async function signupInitiate({ email, username, password, display_name }) {
    try {
        const res = await apiRequest("/signup/initiate", "POST", {
            email,
            username,
            password,
            display_name
        });

        notify("OTP sent to email", "success");
        return res;
    } catch (err) {
        notify(err.message, "error");
        throw err;
    }
}

export async function signupVerify({ email, otp }) {
    try {
        const res = await apiRequest("/signup/verify", "POST", {
            email,
            otp
        });

        currentUser = res.data.user;

        notify("Account created successfully", "success");
        return res;
    } catch (err) {
        notify(err.message, "error");
        throw err;
    }
}

// =========================
// LOGIN
// =========================

export async function login({ identifier, password }) {
    try {
        const res = await apiRequest("/login", "POST", {
            identifier,
            password
        });

        currentUser = res.data.user;

        notify("Login successful", "success");
        return res;
    } catch (err) {
        notify(err.message, "error");
        throw err;
    }
}

// =========================
// LOGOUT
// =========================

export async function logout() {
    try {
        await apiRequest("/logout", "POST");
        currentUser = null;

        notify("Logged out", "success");
    } catch (err) {
        notify(err.message, "error");
    }
}

// =========================
// RESEND OTP
// =========================

export async function resendOtp(email, purpose = "signup") {
    try {
        const res = await apiRequest("/resend-otp", "POST", {
            email,
            purpose
        });

        notify("OTP resent", "success");
        return res;
    } catch (err) {
        notify(err.message, "error");
        throw err;
    }
}

// =========================
// FORGOT PASSWORD
// =========================

export async function forgotPassword(email) {
    try {
        const res = await apiRequest("/forgot-password", "POST", {
            email
        });

        notify("If email exists, OTP sent", "success");
        return res;
    } catch (err) {
        notify(err.message, "error");
        throw err;
    }
}

// =========================
// RESET PASSWORD
// =========================

export async function resetPassword({ email, otp, new_password }) {
    try {
        const res = await apiRequest("/reset-password", "POST", {
            email,
            otp,
            new_password
        });

        notify("Password reset successful", "success");
        return res;
    } catch (err) {
        notify(err.message, "error");
        throw err;
    }
}

// =========================
// AUTO INIT
// =========================

export async function initAuth() {
    try {
        await fetchMe();
    } catch (err) {
        console.log("Auth init failed");
    }
}

// =========================
// EXPORT DEFAULT
// =========================

export default {
    getUser,
    fetchMe,
    signupInitiate,
    signupVerify,
    login,
    logout,
    resendOtp,
    forgotPassword,
    resetPassword,
    initAuth
};