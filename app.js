// ----------------------------
// SUPABASE AUTH
// ----------------------------
const supabaseUrl = "https://ufxjxtgcpidqtjrsovyu.supabase.co";
const supabaseKey = "YOUR_SUPABASE_PUBLIC_KEY";
const supabase = supabase.createClient(supabaseUrl, supabaseKey);

async function getUser() {
  const { data } = await supabase.auth.getUser();
  return data.user;
}

// ----------------------------
// BACKEND URL
// ----------------------------
const API_URL = "https://nest-realtor-backend-22.onrender.com";

// ----------------------------
// DASHBOARD DATA
// ----------------------------
async function loadDashboard() {
  const user = await getUser();
  if (!user) return;

  document.getElementById("userEmail").innerText = user.email;

  const res = await fetch(`${API_URL}/user_plan/${user.id}`);
  const data = await res.json();

  document.getElementById("userPlan").innerText = data.plan;
  document.getElementById("monthlyLeads").innerText = data.total;
  document.getElementById("remainingLeads").innerText = data.remaining;
}

// ----------------------------
// LEAD SEARCH
// ----------------------------
const searchBtn = document.getElementById("searchBtn");
if (searchBtn) {
  searchBtn.addEventListener("click", async () => {
    const location = document.getElementById("leadLocation").value;
    const type = document.getElementById("leadType").value;

    const res = await fetch(`${API_URL}/search_leads`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ location, type }),
    });

    const data = await res.json();
    const box = document.getElementById("leadResults");
    box.innerHTML = "";

    data.results.forEach(item => {
      box.innerHTML += `
        <div class="lead-card">
          <h4>${item.title}</h4>
          <p>${item.price || ""}</p>
          <a href="${item.link}" target="_blank">View Listing</a>
        </div>
      `;
    });
  });
}

// ----------------------------
// CHATBOT
// ----------------------------
const chatSend = document.getElementById("chatSend");
if (chatSend) {
  chatSend.addEventListener("click", async () => {
    const msg = document.getElementById("chatMessage").value;
    const chatBox = document.getElementById("chatBox");

    chatBox.innerHTML += `<p><strong>You:</strong> ${msg}</p>`;
    document.getElementById("chatMessage").value = "";

    const res = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg }),
    });

    const data = await res.json();

    chatBox.innerHTML += `<p><strong>Bot:</strong> ${data.reply}</p>`;
    chatBox.scrollTop = chatBox.scrollHeight;
  });
}

// ----------------------------
// LOGOUT
// ----------------------------
const logoutBtn = document.getElementById("logoutBtn");
if (logoutBtn) {
  logoutBtn.onclick = async () => {
    await supabase.auth.signOut();
    window.location.href = "index.html";
  };
}

// ----------------------------
// AUTO LOAD DASHBOARD
// ----------------------------
window.onload = () => {
  if (document.body.contains(document.getElementById("userPlan"))) {
    loadDashboard();
  }
};
