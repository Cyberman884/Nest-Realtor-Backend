// ✅ Import Firebase SDKs
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js";
import { getAuth, onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js";

// ✅ Your Firebase config (same one from Firebase console)
const firebaseConfig = {
  apiKey: "AIzaSyDc-e04hFYpZ8WDmvFcqBf1zbDfTekGpv8",
  authDomain: "nest-realtor.firebaseapp.com",
  projectId: "nest-realtor",
  storageBucket: "nest-realtor.appspot.com",
  messagingSenderId: "555349990757",
  appId: "1:555349990757:web:35d51938ede7bcf9b6158c",
  measurementId: "G-C4PWJ7QB8E"
};

// ✅ Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// ✅ Watch for login state changes (e.g., dashboard protection)
onAuthStateChanged(auth, (user) => {
  const isDashboard = window.location.pathname.includes("dashboard.html");

  if (isDashboard && !user) {
    // Not logged in → kick out
    alert("Please log in to access your dashboard.");
    window.location.href = "login.html";
  } else if (!isDashboard && user) {
    console.log("User logged in:", user.email);
  }
});

// ✅ Optional logout handler
document.addEventListener("DOMContentLoaded", () => {
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      await signOut(auth);
      alert("You’ve been signed out.");
      window.location.href = "login.html";
    });
  }
});
// ✅ Import Firebase SDKs
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js";
import { getAuth, onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js";

// ✅ Your Firebase config (same one from Firebase console)
const firebaseConfig = {
  apiKey: "AIzaSyDc-e04hFYpZ8WDmvFcqBf1zbDfTekGpv8",
  authDomain: "nest-realtor.firebaseapp.com",
  projectId: "nest-realtor",
  storageBucket: "nest-realtor.appspot.com",
  messagingSenderId: "555349990757",
  appId: "1:555349990757:web:35d51938ede7bcf9b6158c",
  measurementId: "G-C4PWJ7QB8E"
};

// ✅ Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// ✅ Watch for login state changes (e.g., dashboard protection)
onAuthStateChanged(auth, (user) => {
  const isDashboard = window.location.pathname.includes("dashboard.html");

  if (isDashboard && !user) {
    // Not logged in → kick out
    alert("Please log in to access your dashboard.");
    window.location.href = "login.html";
  } else if (!isDashboard && user) {
    console.log("User logged in:", user.email);
  }
});

// ✅ Optional logout handler
document.addEventListener("DOMContentLoaded", () => {
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      await signOut(auth);
      alert("You’ve been signed out.");
      window.location.href = "login.html";
    });
  }
});
