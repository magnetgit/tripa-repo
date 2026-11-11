/* 여행지까지 가는 길 (🟧 11/11) — travel_detail.html 에서 불러 씀
 *
 * 1) 위쪽 패널: [가격 비교] → GET /travel_access/<id>/?people=N → 방법별 카드 (추천·최저가·가장 빠름)
 *    [이걸로 갈게요] → POST /travel_access/<id>/choose/ → 서버가 첫날 출발점·시각·교통 예산·일정을 바꿈
 *    → 화면은 새로 고침 없이 DAY 1 을 다시 불러오고(loadDay) 지도에 가는 길 선을 그림
 * 2) DAY 일정 칸: 첫날 위에 '가는 길', 마지막 날 아래에 '오는 길' 구간 목록
 * 3) 지도: 첫날·마지막 날에 집 → 공항·역·항구 구간을 점선으로
 *
 * 기존 전역(travelId, currentDay, map, loadDay, getCookie, escapeHtml)을 그대로 쓰고,
 * loadDay 를 감싸서 날짜를 바꿀 때마다 구간 목록·지도 선을 다시 그린다.
 */
(function () {
    "use strict";

    const panel = document.getElementById("accessPanel");
    if (!panel) {
        return;
    }

    const ICON = {
        car: "🚗", rental: "🔑", ktx: "🚄", itx: "🚆", bus: "🚌", subway: "🚇", local_bus: "🚌",
        flight: "✈️", ferry: "⛴️", taxi: "🚕", walk: "🚶", wait: "⏳",
    };
    const LINE_COLOR = { flight: "#2d6cdf", ferry: "#0e9aa7", ktx: "#7a4fd6", itx: "#7a4fd6", bus: "#e08a1e" };
    const totalDays = Number(panel.dataset.days) || 1;
    const els = {
        chosen: document.getElementById("acChosen"),
        people: document.getElementById("acPeople"),
        compare: document.getElementById("acCompare"),
        body: document.getElementById("acBody"),
        note: document.getElementById("acNote"),
        grid: document.getElementById("acGrid"),
    };

    let route = readInitialRoute();     // 저장된 access_route (없으면 null)
    let options = [];
    let mapShapes = [];

    function readInitialRoute() {
        const tag = document.getElementById("acRoute");
        try {
            const value = tag ? JSON.parse(tag.textContent) : null;
            return value && typeof value === "object" && Array.isArray(value.go) ? value : null;
        } catch (e) {
            return null;
        }
    }

    const esc = typeof escapeHtml === "function" ? escapeHtml : function (v) {
        return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    };

    function won(n) {
        return Number(n || 0).toLocaleString("ko-KR") + "원";
    }

    function hm(minutes) {
        const m = Math.round(Number(minutes) || 0);
        const h = Math.floor(m / 60);
        return (h ? h + "시간 " : "") + (m % 60 ? (m % 60) + "분" : (h ? "" : "0분"));
    }

    function chainHtml(legs) {
        return legs.map(function (l) {
            return `<span>${ICON[l.mode] || "•"} ${esc(l.label)}</span>`;
        }).join("<i>›</i>");
    }

    /* ------------------------------------------------ 위쪽 패널 */
    function renderChosen() {
        if (!route) {
            els.chosen.innerHTML = "아직 정하지 않았어요 · <b>가격 비교</b>로 집에서 여행지까지 가는 방법을 골라 보세요";
            return;
        }
        const people = route.people ? ` · ${route.people}명` : "";
        const total = route.total ? ` · 왕복 <b>${won(route.total)}</b>` : "";
        els.chosen.innerHTML = `${ICON[(route.go.find(function (l) {
            return ["flight", "ferry", "ktx", "itx", "bus"].indexOf(l.mode) >= 0;
        }) || route.go[0] || {}).mode] || "🧭"} <b>${esc(route.title || "")}</b>${total}${people}`
            + ` · ${esc((route.go[0] || {}).from || "")} → ${esc((route.arrive || {}).name || "")}`;
    }

    function cardHtml(o) {
        const picked = route && route.mode === o.mode;
        const tags = (o.tags || []).map(function (t) {
            return `<span class="ac-tag ac-tag--${t.replace(/\s/g, "")}">${esc(t)}</span>`;
        }).join("") + `<span class="ac-tag ac-tag--real">${o.real ? "실제 시간표" : "어림 시간"}</span>`;
        const items = (o.items || []).map(function (i) {
            return `<li><span>${esc(i.label)}</span><span>${won(i.amount)}</span></li>`;
        }).join("");
        const main = o.go.find(function (l) { return ["flight", "ferry", "ktx", "itx", "bus"].indexOf(l.mode) >= 0; });
        const first = o.go[0] || {};
        return `<article class="ac-card${(o.tags || []).indexOf("추천") >= 0 ? " is-best" : ""}${picked ? " is-picked" : ""}">
            <div class="ac-tags">${tags}</div>
            <h3>${ICON[(main || first).mode] || "🧭"} ${esc(o.title)}</h3>
            <div class="ac-total">${won(o.total)}<small>왕복 · 1인 ${won(o.per_person)}</small></div>
            <div class="ac-meta">${esc(first.depart || "")} 출발 → ${esc(o.ready || "")} 여행 시작 · 가는 데 ${hm(o.minutes)}${main && main.detail ? " · " + esc(main.detail) : ""}</div>
            <div class="ac-chain">${chainHtml(o.go)}</div>
            ${items ? `<ul class="ac-items">${items}</ul>` : ""}
            ${o.note ? `<div class="ac-warn">${esc(o.note)}</div>` : ""}
            <button type="button" class="ac-btn ac-pick" data-mode="${esc(o.mode)}">${picked ? "✓ 지금 이 방법" : "이걸로 갈게요"}</button>
        </article>`;
    }

    function renderCards() {
        els.grid.innerHTML = options.length
            ? options.map(cardHtml).join("")
            : `<div class="ac-empty">비교할 이동 방법이 없어요.</div>`;
    }

    function compare() {
        if (!els.body.hidden && options.length && els.compare.textContent === "접기") {
            els.body.hidden = true;
            els.compare.textContent = "다시 비교";
            return;
        }
        els.body.hidden = false;
        els.compare.disabled = true;
        els.compare.textContent = "비교하는 중…";
        els.note.textContent = "열차·항공·고속버스·여객선 시간표를 찾고 있어요 (처음엔 몇 초 걸려요)";
        els.grid.innerHTML = `<div class="ac-loading">⏳ 불러오는 중…</div>`;
        fetch(`/travel_access/${travelId}/?people=${encodeURIComponent(els.people.value)}`)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) {
                    throw new Error(data.message || "비교하지 못했어요.");
                }
                options = data.options || [];
                if (!data.applicable) {
                    els.note.textContent = data.note || "비교할 방법이 없어요.";
                    els.grid.innerHTML = "";
                    return;
                }
                const city = data.destination ? `${data.origin_city || ""} → ${data.destination}` : "";
                els.note.textContent = `${city} · ${data.people}명 · 왕복 합계 (렌터카는 여행 일수만큼). `
                    + "실제 시간표는 공공데이터(국토교통부·해양교통안전공단) 기준, 없으면 어림이에요.";
                renderCards();
            })
            .catch(function (e) {
                els.note.textContent = e.message || "비교하지 못했어요.";
                els.grid.innerHTML = "";
            })
            .finally(function () {
                els.compare.disabled = false;
                els.compare.textContent = "접기";
            });
    }

    function choose(mode, button) {
        button.disabled = true;
        button.textContent = "반영하는 중…";
        const body = new URLSearchParams({ mode: mode, people: els.people.value });
        fetch(`/travel_access/${travelId}/choose/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "X-CSRFToken": typeof getCookie === "function" ? getCookie("csrftoken") : "",
            },
            body: body.toString(),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) {
                    throw new Error(data.message || "반영하지 못했어요.");
                }
                route = data.route;
                renderChosen();
                renderCards();
                els.body.hidden = true;                       // 고른 뒤에는 접어서 일정 칸이 보이게
                els.compare.textContent = "다시 비교";
                const info = document.querySelector(".travel-summary");
                if (info) {
                    info.querySelectorAll(".summary-value").forEach(function (dd) {
                        if (/^(자동차|대중교통|car|public_transport)$/.test(dd.textContent.trim())) {
                            dd.textContent = route.t_way === "car" ? "자동차" : "대중교통";
                        }
                    });
                }
                // 첫날 일정·지도·비용을 새로 고침 없이 다시 불러옴 (loadDay 감싼 곳에서 구간 목록·선도 다시 그림)
                if (typeof selectDay === "function") {
                    selectDay(1);
                } else if (typeof loadDay === "function") {
                    loadDay(1);
                }
                fitJourney();
            })
            .catch(function (e) {
                alert(e.message || "반영하지 못했어요.");
                button.disabled = false;
                button.textContent = "이걸로 갈게요";
            });
    }

    /* ------------------------------------------------ DAY 일정 칸 */
    function legsHtml(legs, title, back) {
        const fare = legs.reduce(function (s, l) { return s + (Number(l.fare) || 0); }, 0);
        const rows = legs.map(function (l) {
            const detail = [l.detail, l.fare ? won(l.fare) : "", l.overnight ? "다음 날 아침 도착" : ""]
                .filter(Boolean).join(" · ");
            return `<li class="ac-leg ac-leg--${esc(l.mode)}">
                <div class="ac-leg__time">${esc(l.depart || "")}<small>${esc(l.arrive || "")}</small></div>
                <div class="ac-leg__icon">${ICON[l.mode] || "•"}</div>
                <div class="ac-leg__body"><b>${esc(l.label)}</b> ${esc(l.from)} → ${esc(l.to)}
                    <span>${hm(l.minutes)}${detail ? " · " + esc(detail) : ""}</span></div>
            </li>`;
        }).join("");
        const which = back ? "back" : "go";
        const folded = isFolded(which);
        const first = legs[0] || {};
        const last = legs[legs.length - 1] || {};
        const summary = legs.map(function (l) { return (ICON[l.mode] || "") + " " + l.label; }).join(" › ")
            + ` · ${first.depart || ""} → ${last.arrive || ""}`;
        const foot = !back && route && route.ready && route.arrive
            ? `<p class="ac-legs__foot">${esc(route.ready)}부터 ${esc(route.arrive.name)}에서 아래 일정 길안내를 시작해요.</p>`
            : "";
        return `<div class="ac-legs${back ? " ac-legs--back" : ""}${folded ? " is-folded" : ""}" data-which="${which}">
            <button type="button" class="ac-legs__title" aria-expanded="${folded ? "false" : "true"}">
                <span>${title}</span>
                <small>${fare ? won(fare) + " · " : ""}<span class="ac-legs__fold">${folded ? "펼치기 ▾" : "접기 ▴"}</span></small>
            </button>
            <p class="ac-legs__summary">${esc(summary)}</p>
            <ol>${rows}</ol>${foot}</div>`;
    }

    // 접은 상태는 이 브라우저에만 기억 (여행·가는 길/오는 길마다)
    function foldKey(which) {
        return `ac-legs-folded:${travelId}:${which}`;
    }

    function isFolded(which) {
        try {
            return window.localStorage.getItem(foldKey(which)) === "1";
        } catch (e) {
            return false;
        }
    }

    function setFolded(which, folded) {
        try {
            window.localStorage.setItem(foldKey(which), folded ? "1" : "0");
        } catch (e) {
            /* 저장이 막혀 있어도 화면은 바꿈 */
        }
    }

    document.addEventListener("click", function (e) {
        const btn = e.target.closest(".ac-legs__title");
        if (!btn) {
            return;
        }
        const box = btn.closest(".ac-legs");
        const folded = !box.classList.contains("is-folded");
        box.classList.toggle("is-folded", folded);
        btn.setAttribute("aria-expanded", folded ? "false" : "true");
        btn.querySelector(".ac-legs__fold").textContent = folded ? "펼치기 ▾" : "접기 ▴";
        setFolded(box.dataset.which, folded);
    });

    function renderDayLegs(day) {
        const box = document.getElementById("timelineContainer");
        if (!box) {
            return;
        }
        const holder = box.parentElement;
        holder.querySelectorAll(".ac-legs").forEach(function (el) { el.remove(); });
        if (!route) {
            return;
        }
        if (day === 1 && route.go && route.go.length) {
            holder.insertAdjacentHTML("afterbegin", legsHtml(route.go, "🧭 가는 길 · " + esc(route.title || ""), false));
        }
        if (day === totalDays && route.back && route.back.length) {
            holder.insertAdjacentHTML("beforeend", legsHtml(route.back, "🏠 오는 길", true));
        }
    }

    /* ------------------------------------------------ 지도 */
    function clearShapes() {
        mapShapes.forEach(function (s) { s.setMap(null); });
        mapShapes = [];
    }

    function drawJourney(day) {
        clearShapes();
        if (!route || typeof kakao === "undefined" || !kakao.maps || typeof map === "undefined" || !map) {
            return;
        }
        const legs = day === 1 ? route.go : (day === totalDays ? route.back : []);
        (legs || []).forEach(function (l) {
            if (!l.from_pt || !l.to_pt || (l.from_pt[0] === l.to_pt[0] && l.from_pt[1] === l.to_pt[1])) {
                return;
            }
            const big = ["flight", "ferry", "ktx", "itx", "bus"].indexOf(l.mode) >= 0;
            const line = new kakao.maps.Polyline({
                path: [new kakao.maps.LatLng(l.from_pt[0], l.from_pt[1]), new kakao.maps.LatLng(l.to_pt[0], l.to_pt[1])],
                strokeWeight: big ? 4 : 3,
                strokeColor: LINE_COLOR[l.mode] || "#8a97ae",
                strokeOpacity: 0.85,
                strokeStyle: big ? "shortdash" : "dot",
            });
            line.setMap(map);
            mapShapes.push(line);
        });
        const marks = [];
        (legs || []).forEach(function (l, i) {
            if (i === 0 && l.from_pt) {
                marks.push([l.from_pt, ICON[l.mode] + " " + l.from]);
            }
            if (l.to_pt) {
                marks.push([l.to_pt, (ICON[l.mode] || "") + " " + l.to]);
            }
        });
        const seen = {};
        marks.forEach(function (m) {
            const key = m[0].join(",");
            if (seen[key]) {
                return;
            }
            seen[key] = true;
            const label = new kakao.maps.CustomOverlay({
                position: new kakao.maps.LatLng(m[0][0], m[0][1]),
                content: `<div class="ac-map-label">${esc(m[1])}</div>`,
                yAnchor: 1.6,
            });
            label.setMap(map);
            mapShapes.push(label);
        });
    }

    // 고른 직후: 집 ~ 도착지가 다 보이게
    function fitJourney() {
        if (!route || typeof kakao === "undefined" || !map) {
            return;
        }
        const bounds = new kakao.maps.LatLngBounds();
        route.go.forEach(function (l) {
            if (l.from_pt) { bounds.extend(new kakao.maps.LatLng(l.from_pt[0], l.from_pt[1])); }
            if (l.to_pt) { bounds.extend(new kakao.maps.LatLng(l.to_pt[0], l.to_pt[1])); }
        });
        setTimeout(function () { map.setBounds(bounds, 40, 40, 40, 40); }, 900);   // DAY 다시 그린 뒤에
    }

    /* ------------------------------------------------ 기존 loadDay 감싸기 */
    if (typeof loadDay === "function") {
        const originalLoadDay = loadDay;
        // eslint-disable-next-line no-global-assign
        loadDay = function (day) {
            const result = originalLoadDay.apply(this, arguments);
            renderDayLegs(day);
            setTimeout(function () { drawJourney(day); }, 600);      // 장소 선을 그린 뒤 위에
            return result;
        };
    }

    // DAY 일정을 다시 그리면(renderSchedule) 위에 넣은 구간 목록이 지워질 수 있어 다시 붙임
    const timeline = document.getElementById("timelineContainer");
    if (timeline && "MutationObserver" in window) {
        new MutationObserver(function () {
            const holder = timeline.parentElement;
            if (route && !holder.querySelector(".ac-legs") && (currentDay === 1 || currentDay === totalDays)) {
                renderDayLegs(currentDay);
            }
        }).observe(timeline, { childList: true });
    }

    /* ------------------------------------------------ 시작 */
    els.compare.addEventListener("click", compare);
    els.grid.addEventListener("click", function (e) {
        const btn = e.target.closest(".ac-pick");
        if (btn && !btn.disabled) {
            choose(btn.dataset.mode, btn);
        }
    });
    if (route && route.people) {
        els.people.value = String(Math.min(8, route.people));
    }
    renderChosen();
    renderDayLegs(typeof currentDay === "number" ? currentDay : 1);
    setTimeout(function () { drawJourney(typeof currentDay === "number" ? currentDay : 1); }, 1500);
})();
