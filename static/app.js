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
  $("submitBtn").disabled = !(state.geoOk && state.photoFile && $("driver").value && $("mscp").value);
}

function haversineM(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const toRad = d => d * Math.PI / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat/2)**2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2)**2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function selectedMscp() {
  const id = $("mscp").value;
  return (state.seed?.mscps || []).find(m => m.id === id);
}

function recomputeDistance() {
  const sub = $("locSub");
  const farChip = $("farChip");
  const m = selectedMscp();
  if (!state.geoOk) return;
  const parts = [];
  if (m && m.lat != null && m.lon != null) {
    const d = Math.round(haversineM(state.lat, state.lon, m.lat, m.lon));
    const shortAddr = (m.address || m.id).replace(/\s+S\d{6}\s*$/, "");
    parts.push(`${d}m from ${shortAddr}`);
    farChip.classList.toggle("hidden", d <= (state.seed?.far_threshold_m ?? 100));
  } else if (m) {
    parts.push(`MSCP coords not set`);
    farChip.classList.add("hidden");
  } else {
    parts.push("Select MSCP address to check distance");
    farChip.classList.add("hidden");
  }
  if (state.geocode?.postal) parts.push(`Postal ${state.geocode.postal}`);
  sub.textContent = parts.join(" · ");
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
  fillRich(
    $("driver"),
    state.seed.drivers.map(d => ({ value: d.id, label: d.name })),
    "Select driver",
    onDriverChange,
  );
  fillRich(
    $("mscp"),
    state.seed.mscps.map(m => ({ value: m.id, label: m.address || m.id })),
    "Select MSCP address",
    recomputeDistance,
  );
  updateSubmitEnabled();
}

function onDriverChange() {
  const d = (state.seed?.drivers || []).find(x => x.id === $("driver").value);
  $("agencyVal").textContent = d?.agency || "—";
}

function fillRich(sel, items, placeholder, onChange) {
  sel.innerHTML = "";
  const ph = document.createElement("option");
  ph.value = ""; ph.textContent = placeholder; ph.disabled = true; ph.selected = true;
  sel.appendChild(ph);
  items.forEach(({ value, label }) => {
    const o = document.createElement("option");
    o.value = value; o.textContent = label;
    sel.appendChild(o);
  });
  sel.classList.add("unset");
  sel.addEventListener("change", () => {
    sel.classList.toggle("unset", !sel.value);
    if (onChange) onChange();
    updateSubmitEnabled();
  });
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
      } catch (e) {
        $("locAddr").textContent = `${state.lat.toFixed(5)}, ${state.lon.toFixed(5)}`;
      }
      recomputeDistance();
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
$("photo").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const url = URL.createObjectURL(f);
  const img = $("preview");
  img.src = url;
  img.classList.remove("hidden");
  $("dropzone").querySelector(".dz-icon").classList.add("hidden");
  $("dropzone").querySelector(".dz-title").classList.add("hidden");
  $("dropzone").querySelector(".dz-sub").classList.add("hidden");
  // Compress client-side to keep upload fast/reliable
  try {
    state.photoFile = await compressImage(f, 1600, 0.82);
  } catch (err) {
    state.photoFile = f;  // fall back to original on any failure
  }
  updateSubmitEnabled();
});

async function compressImage(file, maxEdge, quality) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));
  const w = Math.round(bitmap.width * scale);
  const h = Math.round(bitmap.height * scale);
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  canvas.getContext("2d").drawImage(bitmap, 0, 0, w, h);
  const blob = await new Promise(res => canvas.toBlob(res, "image/jpeg", quality));
  return new File([blob], file.name.replace(/\.\w+$/, ".jpg"), { type: "image/jpeg" });
}

// ============== submit ==============
$("submitBtn").addEventListener("click", async () => {
  const btn = $("submitBtn");
  btn.disabled = true;
  btn.textContent = "Submitting…";

  const fd = new FormData();
  fd.append("driver_id", $("driver").value);
  fd.append("mscp_id", $("mscp").value);
  fd.append("lat", state.lat);
  fd.append("lon", state.lon);
  fd.append("photo", state.photoFile);

  try {
    const r = await fetch("/api/submit", { method: "POST", body: fd });
    const text = await r.text();
    let data = {};
    try { data = JSON.parse(text); } catch (_) {
      throw new Error(`HTTP ${r.status}: ${text.slice(0, 200)}`);
    }
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
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
