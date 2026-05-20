// ============== state ==============
const state = {
  seed: null,
  lat: null,
  lon: null,
  geoOk: false,
  photoFile: null,
  geocode: null,
};

// ============== utilities ==============
function $(id) { return document.getElementById(id); }

function setDatePill() {
  const d = new Date();
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  $("datePill").textContent = `${d.getDate()} ${months[d.getMonth()]}`;
}

function toast(msg, kind) {
  const el = $("toast");
  el.textContent = msg;
  el.className = "toast " + (kind || "");
  setTimeout(() => el.classList.add("hidden"), 3500);
  el.classList.remove("hidden");
}

function updateSubmitEnabled() {
  $("submitBtn").disabled = !(state.geoOk && state.photoFile && $("driver").value && $("agency").value && $("mscp").value);
}

// ============== tabs ==============
document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    $("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "history") loadHistory();
  });
});

// ============== seed + dropdowns ==============
async function loadSeed() {
  const r = await fetch("/api/seed");
  state.seed = await r.json();
  fill($("driver"), state.seed.drivers);
  fill($("agency"), state.seed.agencies);
  fill($("mscp"), state.seed.mscps.map(m => m.id));
  updateSubmitEnabled();
}

function fill(sel, items) {
  sel.innerHTML = "";
  items.forEach(v => {
    const o = document.createElement("option");
    o.value = v; o.textContent = v;
    sel.appendChild(o);
  });
  sel.addEventListener("change", updateSubmitEnabled);
}

// ============== geolocation ==============
function locate() {
  if (!navigator.geolocation) {
    $("locAddr").textContent = "Geolocation not supported";
    return;
  }
  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      state.lat = pos.coords.latitude;
      state.lon = pos.coords.longitude;
      state.geoOk = true;
      $("latVal").textContent = state.lat.toFixed(6);
      $("lonVal").textContent = state.lon.toFixed(6);
      $("locSub").textContent = "Resolving address…";
      try {
        const r = await fetch(`/api/geocode?lat=${state.lat}&lon=${state.lon}`);
        const g = await r.json();
        state.geocode = g;
        $("locAddr").textContent = g.address || `${state.lat.toFixed(5)}, ${state.lon.toFixed(5)}`;
        const subBits = [];
        if (g.distance_m !== undefined) subBits.push(`${g.distance_m}m away`);
        if (g.postal) subBits.push(`Postal ${g.postal}`);
        $("locSub").textContent = subBits.join(" · ") || "Located";
        $("farChip").classList.toggle("hidden", !g.far);
        if (g.nearest_mscp) $("mscp").value = g.nearest_mscp.id;
      } catch (e) {
        $("locAddr").textContent = `${state.lat.toFixed(5)}, ${state.lon.toFixed(5)}`;
        $("locSub").textContent = "Address lookup failed";
      }
      updateSubmitEnabled();
    },
    (err) => {
      $("locAddr").textContent = "Location unavailable";
      $("locSub").textContent = err.message || "Permission denied";
    },
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
  );
}

// ============== photo ==============
$("photo").addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (!f) return;
  state.photoFile = f;
  const url = URL.createObjectURL(f);
  const img = $("preview");
  img.src = url;
  img.classList.remove("hidden");
  $("dropzone").querySelector(".dz-icon").classList.add("hidden");
  $("dropzone").querySelector(".dz-title").classList.add("hidden");
  $("dropzone").querySelector(".dz-sub").classList.add("hidden");
  updateSubmitEnabled();
});

// ============== submit ==============
$("submitBtn").addEventListener("click", async () => {
  const btn = $("submitBtn");
  btn.disabled = true;
  btn.textContent = "Submitting…";

  const fd = new FormData();
  fd.append("driver_id", $("driver").value);
  fd.append("agency", $("agency").value);
  fd.append("mscp_id", $("mscp").value);
  fd.append("lat", state.lat);
  fd.append("lon", state.lon);
  fd.append("photo", state.photoFile);

  try {
    const r = await fetch("/api/submit", { method: "POST", body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Submit failed");
    toast(`Submitted — ${data.status}`, "ok");
    // reset photo
    state.photoFile = null;
    $("photo").value = "";
    $("preview").classList.add("hidden");
    $("dropzone").querySelector(".dz-icon").classList.remove("hidden");
    $("dropzone").querySelector(".dz-title").classList.remove("hidden");
    $("dropzone").querySelector(".dz-sub").classList.remove("hidden");
  } catch (e) {
    toast(e.message, "err");
  } finally {
    btn.textContent = "Submit Sortation Check";
    updateSubmitEnabled();
  }
});

// ============== history ==============
async function loadHistory() {
  const list = $("historyList");
  list.innerHTML = `<div class="empty">Loading…</div>`;
  try {
    const r = await fetch("/api/history");
    const data = await r.json();
    const rows = data.rows || [];
    if (!rows.length) {
      list.innerHTML = `<div class="empty">No submissions yet</div>`;
      return;
    }
    list.innerHTML = "";
    rows.forEach(row => {
      const status = row["Status"] || "Valid";
      const chipClass = status === "Valid" ? "chip-valid" : "chip-warn";
      const ts = row["Timestamp"] || "";
      const rawAddr = row["Address"] || `${row["Lat"]}, ${row["Long"]}`;
      const addr = rawAddr.replace(/\s+S\d{6}\s*$/, "");  // strip postal suffix for list view
      const agency = row["Agency"] || "";
      const short = ts ? formatShort(ts) : "";
      const item = document.createElement("div");
      item.className = "history-item";
      item.innerHTML = `
        <div>
          <div class="h-main">${escapeHtml(addr)}</div>
          <div class="h-sub">${escapeHtml(short)} · ${escapeHtml(agency)}</div>
        </div>
        <div class="chip ${chipClass}">${escapeHtml(status)}</div>
      `;
      list.appendChild(item);
    });
  } catch (e) {
    list.innerHTML = `<div class="empty">Failed to load history</div>`;
  }
}

function formatShort(ts) {
  // ts like "2026-05-20 09:14:00" or "2026-05-20 9:14:00" (Sheets may strip leading zeros)
  const m = ts.match(/^(\d{4})-(\d{1,2})-(\d{1,2}) (\d{1,2}):(\d{2})/);
  if (!m) return ts;
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const d = parseInt(m[3], 10);
  const mo = months[parseInt(m[2], 10) - 1];
  let h = parseInt(m[4], 10);
  const mm = m[5];
  const ap = h >= 12 ? "PM" : "AM";
  h = h % 12 || 12;
  return `${d} ${mo}, ${h}:${mm} ${ap}`;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}

// ============== boot ==============
setDatePill();
loadSeed();
locate();
