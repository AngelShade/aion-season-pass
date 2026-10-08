(function () {
    'use strict';
    var state = null, page = 0, view = 'rewards', cadence = 'DAILY', busy = false, modalAction = null, retryAction = null, focusBefore = null;
    var token = query('session_id'), tracks = ['Free', 'Premium', 'Advanced'], serverOffset = 0, readRequest = null, rendered = {};
    function el(id) { return document.getElementById(id); }
    function setText(id, value) { var node = el(id), text = String(value); if (node.textContent !== text) node.textContent = text; }
    function query(name) { var m = new RegExp('(?:^|&)' + name + '=([^&]*)').exec(location.search.substring(1)); return m ? decodeURIComponent(m[1].replace(/\+/g, ' ')) : ''; }
    function escape(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
    function money(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
    function shortName(s) { return s.replace('[Emotion Card] ', '').replace('Dye: ', ''); }
    function date(n) { var d = new Date(n), months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']; return d.getDate() + ' ' + months[d.getMonth()] + ' ' + d.getFullYear(); }
    function remaining(n) { var ms = Math.max(0, n - (new Date().getTime() + serverOffset)); var d = Math.floor(ms / 86400000), h = Math.floor(ms / 3600000) % 24, m = Math.floor(ms / 60000) % 60; return (d ? d + 'd ' : '') + h + 'h ' + m + 'm'; }
    function status(text, error) { setText('status', text); el('connection-dot').className = 'connection-dot ' + (error ? 'error' : 'online'); }
    function itemTooltip(r) { return 'nc://aion.ItemInfo/ItemTooltip?item=' + Number(r.item) + '&count=' + Number(r.quantity || r.min || 1) + '&enchant_count=0&authorize_count=0'; }
    function icon(r, cls) { var tip = escape(itemTooltip(r)); return '<a class="native-item-icon" href="' + tip + '" title="' + tip + '" onclick="return false" tabindex="-1"><img class="' + (cls || '') + '" title="' + tip + '" src="/market/media/icons/' + r.item + '.png?v=native-3" alt="' + escape(r.name) + '"></a>'; }
    function rewardDescription(r) {
        var descriptions = {
            186000237: 'Exchange Ancient Coins at Ancient Coin merchants for equipment and supplies.',
            186000236: 'Exchange Blood Marks at Blood Mark merchants for equipment and supplies.',
            166020000: 'Enchants equipment and amplifies eligible equipment. Enchantment can fail.',
            166030013: 'Tempers eligible accessories and plumes. Tempering can fail.',
            188053666: 'Open each box to receive 1–3 Ceramium Medals at random. Ceramium Medals are used to buy Abyss equipment.',
            188052741: 'Open each bundle and choose 1 of 18 level-60 Composite Manastones. The choices are listed below.',
            166150019: 'Guarantees a successful manastone socketing attempt on eligible Mythic equipment up to level 65. Consumes one aid per attempt.',
            110900234: 'Dynasty Light Armor appearance for equipment remodeling. Permanent [Event] edition.',
            110900233: 'Dynasty Heavy Armor appearance for equipment remodeling. Permanent [Event] edition.',
            188053321: 'Open each chest and choose 1 Attack or Magic Boost Empyrean Plume for your faction.',
            190100151: 'Permanent Shugo Gyrocopter mount. Requires level 60. Cannot be traded.',
            188052319: 'Open the box to receive Tiamat\'s Spectral Wings. Permanent wings; requires level 60.',
            190020133: 'Adopt a permanent Stormwing pet. Provides auto-looting and automatic use of food and scrolls.',
            188053646: 'Open the box and choose 1 level-65 Mythic Nether Dragon King weapon or shield from the 14 items listed below.'
        };
        return descriptions[r.item] || r.description.replace(/native /gi, '').replace('Duplicate copies are used for 4.8 stigma charging.', 'Use duplicate stigmas for Stigma Enchantment.');
    }
    function reward(level, track) { for (var i = 0; i < state.rewards.length; i++) if (state.rewards[i].level === level && state.rewards[i].track === track) return state.rewards[i]; return null; }
    function crest(track, cls) { return '<img class="' + (cls || 'track-crest') + '" src="/market/pass/media/' + (track === 2 ? 'ascendant-crest.png' : 'aether-crest.png') + '?v=5" alt="">'; }
    function frame(name) { return '<img class="art-frame" src="/market/pass/media/' + (name || 'aether-frame') + '.png?v=5" alt="">'; }
    function request(method, args, success) {
        var xhr = new XMLHttpRequest(), parts = [], k;
        args.session_id = token;
        for (k in args) if (args.hasOwnProperty(k)) parts.push(encodeURIComponent(k) + '=' + encodeURIComponent(args[k]));
        var body = parts.join('&');
        xhr.open(method, '/market/pass/' + (method === 'GET' ? 'state?' + body : 'action'), true);
        if (method === 'GET') { if (readRequest) readRequest.abort(); readRequest = xhr; }
        else if (readRequest) { readRequest.abort(); readRequest = null; }
        xhr.timeout = 20000;
        if (method === 'POST') xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
        function fail(message) {
            busy = false; el('dialog-confirm').disabled = false;
            if (method === 'POST' && retryAction) el('retry').className = 'quiet';
            el('dialog-error').textContent = message; status(message, true);
        }
        xhr.onload = function () {
            if (method === 'GET' && readRequest !== xhr) return;
            if (method === 'GET') readRequest = null;
            var data; try { data = JSON.parse(xhr.responseText); } catch (e) { fail('Could not read the response. Refresh the pass.'); return; }
            if (xhr.status !== 200 || data.error) { fail(data.error || 'The request failed. Refresh before trying again.'); return; }
            success(data);
        };
        xhr.onerror = function () { fail('Connection lost. Retry the last action to check its result.'); };
        xhr.ontimeout = function () { fail('The response timed out. Retry the last action to check its result.'); };
        xhr.send(method === 'POST' ? body : null);
    }
    function apply(data) {
        state = data; serverOffset = data.now - new Date().getTime();
        setText('character', data.character);
        setText('wallet', money(data.kinah) + ' Kinah');
        setText('server-name', data.season.serverName.toUpperCase());
        document.title = data.season.serverName + ' Season Pass';
        setText('season-name', data.season.name);
        setText('subtitle', 'Complete daily, weekly and season missions to earn Season XP.');
        setText('level', data.level); setText('level-max', '/ ' + data.season.levels);
        var xp = data.xp % data.season.xpPerLevel, max = data.level === data.season.levels;
        setText('xp-label', max ? 'Season complete · ' + money(data.xp) + ' XP' : money(xp) + ' / ' + money(data.season.xpPerLevel) + ' XP');
        var fill = (max ? 100 : xp * 100 / data.season.xpPerLevel) + '%'; if (el('xp-fill').style.width !== fill) el('xp-fill').style.width = fill;
        setText('completion', Math.floor(data.level * 100 / data.season.levels) + '%');
        setText('end-date', date(data.ends - 1));
        setText('owned-tier', ['Free Pass','Premium Pass','Advanced Premium'][data.tier]);
        setText('upgrade-shortcut', data.tier === 2 ? 'All tracks unlocked' : data.tier === 1 ? 'Explore Advanced Premium' : 'Explore Premium');
        el('upgrade-shortcut').disabled = data.tier === 2;
        setText('claim-deadline', 'Claim earned rewards until ' + date(data.claimsEnd - 1));
        var count = 0; for (var i = 0; i < data.rewards.length; i++) if (data.rewards[i].available) count++;
        setText('ready-count', count ? count : '');
        el('claim-all').disabled = !count || !data.claimable;
        setText('claim-all', count ? 'Claim available (' + count + ')' : 'No rewards to claim');
        setText('next-reward', max ? 'Level 30 reached. Claim remaining rewards.' : 'Next rewards unlock at level ' + (data.level + 1) + '.');
        renderCurrent(); timer();
        status(data.notice || (data.active ? 'Progress saved automatically · Free Pass is active' : data.claimable ? 'Season ended · Claim your earned rewards before the deadline' : data.now < data.starts ? 'The season has not started yet' : 'Season closed · Claims have ended'), false);
    }
    function load(initial) {
        if (busy) return;
        request('GET', {}, function (data) { if (initial) page = Math.min(Math.floor(data.level / 5), Math.ceil(data.season.levels / 5) - 1); apply(data); });
    }
    function renderCurrent() {
        if (!state) return;
        var data;
        if (view === 'rewards') data = [page, state.level, state.tier, state.claimable, state.season.levels, state.rewards];
        else if (view === 'missions') data = [cadence, state.active, state.ends, state.missions];
        else if (view === 'passes') {
            var definitions = []; for (var i = 0; i < state.rewards.length; i++) { var r = state.rewards[i]; definitions.push([r.level, r.track, r.item, r.quantity, r.name]); }
            data = [state.season, state.tier, state.active, definitions];
        } else data = [state.history, state.rewards];
        var key = JSON.stringify(data);
        if (rendered[view] !== key) {
            if (view === 'rewards') renderTrack(); else if (view === 'missions') renderMissions(); else if (view === 'passes') renderPasses(); else renderHistory();
            rendered[view] = key;
        }
        if (view === 'missions') updateMissionReset();
    }
    function renderTrack() {
        var start = page * 5 + 1, end = Math.min(start + 4, state.season.levels), html = '<table class="reward-table"><thead><tr><th class="row-label"></th>', i, t, r;
        for (i = start; i <= end; i++) html += '<th class="' + (i === state.level ? 'current' : i < state.level ? 'achieved' : '') + (i % 5 === 0 ? ' milestone-level' : '') + '"><span>' + (i <= state.level ? '✓ ' : '') + 'LEVEL ' + i + '</span></th>';
        html += '</tr></thead><tbody>';
        for (t = 0; t < 3; t++) {
            html += '<tr><td class="row-label ' + (t === 1 ? 'premium' : t === 2 ? 'advanced' : '') + '">' + crest(t) + '<strong>' + (t === 2 ? 'Advanced' : tracks[t]) + '</strong><span class="track-access">' + (t <= state.tier ? '✓ TRACK UNLOCKED' : 'PREMIUM TRACK · LOCKED') + '</span><span class="track-count">' + (t === 0 ? 'Free for every Daeva' : t === 1 ? 'Premium collection' : 'Advanced Premium collection') + '</span></td>';
            for (i = start; i <= end; i++) {
                r = reward(i, t); if (!r) continue;
                var flag = r.claimed ? 'Claimed ✓' : r.available ? 'Claim reward' : r.track > state.tier ? tracks[r.track] + ' locked' : r.needsClass ? 'Ascend first' : 'Level ' + i + ' required';
                html += '<td><button data-reward="' + i + ':' + t + '" class="reward-cell ' + (t === 1 ? 'premium-frame ' : t === 2 ? 'advanced-frame ' : '') + (i % 5 === 0 ? 'milestone-cell ' : '') + (r.claimed ? 'claimed' : r.available ? 'available' : r.track > state.tier ? 'paid' : '') + '" title="' + escape(itemTooltip(r)) + '">' + frame() + (i % 5 === 0 ? '<span class="milestone-star">✦</span>' : '') + (r.track > state.tier ? '<span class="lock-mark">◇</span>' : '') + '<span class="icon-well">' + icon(r, 'item-icon') + '<span class="quantity">×' + r.quantity + '</span></span><strong>' + escape(shortName(r.name)) + '</strong><span class="reward-state">' + flag + '</span></button></td>';
            }
            html += '</tr>';
        }
        el('track').innerHTML = html + '</tbody></table>';
        el('page-label').textContent = 'Levels ' + start + '–' + end;
        el('previous').disabled = page === 0; el('next').disabled = end === state.season.levels;
        var chapters = '';
        for (i = 0; i < Math.ceil(state.season.levels / 5); i++) chapters += '<button data-chapter="' + i + '" class="' + (i === page ? 'current' : (i + 1) * 5 <= state.level ? 'earned' : '') + '" title="View levels ' + (i * 5 + 1) + ' to ' + Math.min((i + 1) * 5, state.season.levels) + '">' + (i * 5 + 1) + '–' + Math.min((i + 1) * 5, state.season.levels) + '<span>' + ((i + 1) * 5 <= state.level ? '✓' : '✦') + '</span></button>';
        el('chapter-navigation').innerHTML = chapters;
        html = ''; for (t = 0; t < 3; t++) { r = reward(state.season.levels, t); html += '<button class="' + (t === 1 ? 'premium-frame' : t === 2 ? 'advanced-frame' : '') + '" data-reward="' + r.level + ':' + t + '" title="' + escape(itemTooltip(r)) + '">' + icon(r) + '<small>' + tracks[t].toUpperCase() + ' FINALE</small><strong>' + escape(shortName(r.name)) + '</strong><span class="final-level">LEVEL ' + state.season.levels + '</span></button>'; }
        el('final-rewards').innerHTML = html;
    }
    function renderMissions() {
        var html = '', count = 0, complete = 0, reset = state.ends;
        var overview = '', periods = ['DAILY','WEEKLY','SEASON'];
        for (var p = 0; p < periods.length; p++) {
            var done = 0, total = 0, earned = 0, allXp = 0;
            for (var x = 0; x < state.missions.length; x++) { var mission = state.missions[x]; if (mission.cadence !== periods[p]) continue; total++; allXp += mission.xp; if (mission.complete) { done++; earned += mission.xp; } }
            overview += '<div class="mission-stat"><span>' + periods[p] + ' MISSIONS</span><strong>' + done + '</strong><small>/ ' + total + '</small><span class="stat-xp">' + money(earned) + ' / ' + money(allXp) + ' XP</span><div class="meter"><i style="width:' + (total ? done * 100 / total : 0) + '%"></i></div></div>';
        }
        el('mission-overview').innerHTML = overview;
        for (var i = 0; i < state.missions.length; i++) {
            var m = state.missions[i]; if (cadence !== 'ALL' && m.cadence !== cadence) continue;
            count++; if (m.complete) complete++; reset = Math.min(reset, m.reset);
            html += '<article class="mission-row ' + (m.complete ? 'complete' : '') + '"><span class="mission-icon">' + (m.complete ? '✓' : '◇') + '</span><h3>' + escape(m.name) + (cadence === 'ALL' ? ' <small>· ' + m.cadence.toLowerCase() + '</small>' : '') + '</h3><p>' + escape(m.description) + '</p><div class="meter"><i style="width:' + Math.min(100, m.progress * 100 / m.target) + '%"></i></div><div class="mission-summary"><strong>+' + money(m.xp) + ' XP</strong><small>' + money(m.progress) + ' / ' + money(m.target) + '</small><span class="mission-status">' + (m.complete ? 'XP awarded' : state.active ? 'In progress' : 'Closed') + '</span></div></article>';
        }
        el('mission-list').innerHTML = html;
        updateMissionReset();
    }
    function updateMissionReset() {
        var count = 0, complete = 0, reset = state.ends;
        for (var i = 0; i < state.missions.length; i++) { var m = state.missions[i]; if (cadence !== 'ALL' && m.cadence !== cadence) continue; count++; if (m.complete) complete++; reset = Math.min(reset, m.reset); }
        setText('mission-reset', complete + '/' + count + ' complete · ' + (state.active ? (cadence === 'SEASON' ? 'Ends in ' : 'Resets in ') + remaining(reset) : 'Season ended'));
    }
    function trackContents(track) {
        var totals = {}, stigma = 0, list = [], i, r;
        for (i = 0; i < state.rewards.length; i++) {
            r = state.rewards[i]; if (r.track !== track) continue;
            if (/Stigma Bundle|Class Stigma/.test(r.name)) stigma += r.quantity;
            else totals[r.item] = (totals[r.item] || 0) + r.quantity;
        }
        var materials = [[186000237, 'Ancient Coins'], [186000236, 'Blood Marks'], [166020000, 'Omega Enchantment Stones'], [166030013, '[Event] Tempering Solutions'], [166150019, 'Assured Greater Felicitous Socketing (Mythic)'], [188053666, 'Ceramium Medal Boxes (1–3 medals each)'], [188052741, 'Composite Manastone Bundles (choose 1 per bundle)']];
        for (i = 0; i < materials.length; i++) if (totals[materials[i][0]]) list.push(totals[materials[i][0]] + ' × ' + materials[i][1]);
        if (stigma) list.push(stigma + ' × class Stigma Bundles (1 random stigma each)');
        for (i = 0; i < state.rewards.length; i++) {
            r = state.rewards[i]; if (r.track !== track || !totals[r.item]) continue;
            var ordinary = false;
            for (var j = 0; j < materials.length; j++) if (materials[j][0] === r.item) ordinary = true;
            if (!ordinary) { list.push(totals[r.item] + ' × ' + r.name + ' (level ' + r.level + ')'); delete totals[r.item]; }
        }
        return list;
    }
    function renderPasses() {
        var s = state.season, html = '', prices = [0, s.premiumKinah, s.advancedKinah - (state.tier === 1 ? s.premiumKinah : 0)], descriptions = [trackContents(0), trackContents(1), trackContents(2)];
        for (var t = 0; t < 3; t++) {
            var owned = state.tier >= t;
            html += '<article class="pass-card ' + (t === 1 ? 'premium' : t === 2 ? 'advanced' : '') + '"><div class="pass-shell">' + frame('pass-panel') + '<div class="pass-illustration">' + crest(t, 'pass-crest') + '</div><span class="ribbon">' + (t === 0 ? 'FREE REWARD TRACK' : t === 1 ? 'FREE + PREMIUM TRACKS' : 'ALL THREE REWARD TRACKS') + '</span><h3>' + (t === 2 ? 'Advanced Premium' : tracks[t] + ' Pass') + '</h3><div class="price">' + (t === 0 ? 'Free' : money(prices[t])) + (t ? '<small>Kinah' + (t === 2 && state.tier === 1 ? ' · upgrade' : '') + '</small>' : '') + '</div><p class="track-includes">' + (t === 0 ? '30 Free rewards. Complete missions to earn Season XP.' : t === 1 ? 'Includes the Free track plus these 30 Premium rewards:' : 'Includes Free and Premium, plus these 30 Advanced rewards and a one-time ' + s.advancedLevels + '-level boost:') + '</p><ul>';
            for (var j = 0; j < descriptions[t].length; j++) html += '<li>' + escape(descriptions[t][j]) + '</li>';
            var finale = reward(s.levels, t);
            html += '</ul><div class="showcase">' + icon(finale) + '<small>LEVEL ' + s.levels + ' FINALE</small><strong>' + escape(shortName(finale.name)) + '</strong></div><button data-buy="' + t + '" class="' + (owned ? 'owned' : 'gold') + '" ' + (owned || !state.active ? 'disabled' : '') + '>' + (owned ? '✓ Unlocked' : !state.active ? 'Purchases closed' : t === 2 && state.tier === 1 ? 'Upgrade to Advanced' : 'Unlock ' + tracks[t]) + '</button></div></article>';
        }
        el('pass-options').innerHTML = html;
    }
    function renderHistory() {
        var html = '';
        for (var i = 0; i < state.history.length; i++) {
            var h = state.history[i], r = reward(h.reward_level, h.track);
            html += '<article class="history-row">' + icon({ item: h.item_id, name: r ? r.name : 'Season reward' }) + '<h3>' + escape(r ? r.name : 'Season reward') + ' ×' + h.quantity + '</h3><p>Level ' + h.reward_level + ' · ' + tracks[h.track] + ' · Delivered to Black Cloud mail</p><time>' + date(h.claimed_at) + '</time></article>';
        }
        el('history-list').innerHTML = html || '<div class="empty"><h3>No rewards claimed</h3><p>Claim an earned reward and its delivery will appear here.</p></div>';
    }
    function timer() {
        if (!state) return;
        setText('countdown', state.active ? remaining(state.ends) + ' remaining' : state.claimable ? 'Claim period · ' + remaining(state.claimsEnd) + ' left' : state.now < state.starts ? 'Begins ' + date(state.starts) : 'Season closed');
    }
    function showView(name) {
        view = name; var buttons = document.querySelectorAll('.tabs button');
        for (var i = 0; i < buttons.length; i++) buttons[i].className = buttons[i].getAttribute('data-view') === name ? 'active' : '';
        var names = ['rewards','missions','passes','history']; for (i = 0; i < names.length; i++) el(names[i] + '-view').className = 'view ' + (names[i] === name ? '' : 'hidden');
        renderCurrent();
    }
    function openDialog(kicker, title, body, action, label, disabled) {
        focusBefore = document.activeElement; modalAction = action;
        el('dialog-kicker').textContent = kicker; el('dialog-title').textContent = title;
        el('dialog-body').innerHTML = body; el('dialog-error').textContent = '';
        el('dialog-confirm').textContent = label || 'Confirm'; el('dialog-confirm').disabled = !!disabled;
        el('shade').className = 'shade'; el('dialog-cancel').focus();
        document.querySelector('.dialog').scrollTop = 0;
    }
    function closeDialog() { if (busy) return; el('shade').className = 'shade hidden'; modalAction = null; if (focusBefore && focusBefore.focus) focusBefore.focus(); }
    function inspect(level, track) {
        if (!state || busy) return;
        var r = reward(level, track), action = null, label = 'Locked', disabled = false;
        var body = '<div class="detail-body">' + icon(r, 'dialog-item') + '<p>' + escape(rewardDescription(r)) + '</p><p class="muted">' + tracks[track] + ' track · Level ' + level + ' · Receive ×' + r.quantity + ' · Item level ' + r.requiredLevel + '</p></div>';
        if (r.box && r.box.items.length && !r.needsClass) {
            body += '<div class="box-preview"><h4>' + (r.box.mode === 'choice' ? 'Choose one when you open the box' : r.box.mode === 'random' ? 'One random item per bundle' : 'Inside each box') + '</h4><div class="box-items">';
            for (var b = 0; b < r.box.items.length; b++) {
                var inside = r.box.items[b], amount = inside.min === inside.max ? inside.min : inside.min + '–' + inside.max;
                body += '<div class="box-item">' + icon(inside, 'box-icon') + '<strong>' + escape(shortName(inside.name)) + '</strong><small>×' + amount + ' · Item level ' + inside.requiredLevel + '</small></div>';
            }
            body += '</div><p class="muted">Collect the reward from mail, then open it in your Inventory.</p></div>';
        }
        if (r.available) { action = { action: 'claim', level: level, track: track }; label = 'Claim reward'; body += '<p class="cost-row">Delivered to Black Cloud mail. No Kinah cost.</p>'; }
        else if (r.claimed) { label = 'Already claimed'; disabled = true; body += '<p class="cost-row">This reward has already been delivered.</p>'; }
        else if (!state.claimable) { label = 'Claims closed'; disabled = true; }
        else if (track > state.tier) { label = 'Explore passes'; action = { navigate: 'passes' }; body += '<p class="cost-row">Own ' + (track === 2 ? 'Advanced Premium' : 'Premium') + ' and earn level ' + level + ' to claim this reward.</p>'; }
        else if (r.needsClass) { label = 'Ascend first'; disabled = true; body += '<p class="cost-row">Choose your advanced class before claiming this stigma bundle. Your reward stays reserved.</p>'; }
        else { label = 'Earn level ' + level; disabled = true; body += '<p class="cost-row">Complete missions to earn more Season XP.</p>'; }
        openDialog(tracks[track].toUpperCase() + ' REWARD · LEVEL ' + level, r.name, body, action, label, disabled);
    }
    function buy(tier) {
        if (!state || !state.active || tier <= state.tier || busy) return;
        var cost = (tier === 2 ? state.season.advancedKinah : state.season.premiumKinah) - (state.tier === 1 ? state.season.premiumKinah : 0);
        var boost = Math.min(state.season.advancedLevels, state.season.levels - state.level);
        var body = '<p>Unlock ' + (tier === 2 ? 'both paid reward tracks' : 'the Premium reward track') + ' for <strong>' + escape(state.character) + '</strong> this season. Earlier earned rewards become claimable immediately.</p>';
        if (tier === 2) body += '<div class="boost">One-time boost: level ' + state.level + ' → ' + (state.level + boost) + '. ' + (boost < state.season.advancedLevels ? 'The boost stops at the final level; unused levels are not refunded.' : 'Mission progress is kept.') + '</div>';
        body += '<p class="cost-row">Purchase cost <b>' + money(cost) + ' Kinah</b></p><p>Inventory balance <b>' + money(state.kinah) + ' Kinah</b></p><p class="muted">Purchases are final for this character and season. Progress closes ' + date(state.ends - 1) + '.</p>';
        openDialog('KINAH PURCHASE', 'Unlock ' + (tier === 2 ? 'Advanced Premium' : 'Premium'), body, { action: 'purchase', tier: tier }, state.kinah < cost ? 'Not enough Kinah' : 'Pay ' + money(cost) + ' Kinah', state.kinah < cost);
    }
    function submit(args, retry) {
        if (!state || busy) return;
        if (args.navigate) { closeDialog(); showView(args.navigate); return; }
        busy = true; el('dialog-confirm').disabled = true;
        var payload = {}, k; for (k in args) if (args.hasOwnProperty(k)) payload[k] = args[k];
        if (!retry) payload.request = state.request;
        retryAction = payload; el('retry').className = 'quiet hidden'; status('Saving your selection…', false);
        request('POST', payload, function (data) { busy = false; retryAction = null; closeDialog(); apply(data); el('retry').className = 'quiet hidden'; });
    }
    document.addEventListener('click', function (event) {
        var button = event.target; while (button && button !== document && button.tagName !== 'BUTTON') button = button.parentNode;
        if (!button || button === document || button.disabled || busy) return;
        var tab = button.getAttribute('data-view'), filter = button.getAttribute('data-cadence'), slot = button.getAttribute('data-reward'), tier = button.getAttribute('data-buy');
        if (tab) showView(tab);
        if (filter) { cadence = filter; var buttons = el('mission-filters').getElementsByTagName('button'); for (var i = 0; i < buttons.length; i++) buttons[i].className = buttons[i] === button ? 'active' : ''; renderCurrent(); }
        if (slot) { var parts = slot.split(':'); inspect(Number(parts[0]), Number(parts[1])); }
        if (tier !== null) buy(Number(tier));
        var chapter = button.getAttribute('data-chapter'); if (chapter !== null && state) { page = Number(chapter); renderCurrent(); }
    });
    el('refresh').onclick = function () { load(false); };
    el('upgrade-shortcut').onclick = function () { showView('passes'); };
    el('previous').onclick = function () { if (state && page > 0) { page--; renderCurrent(); } };
    el('next').onclick = function () { if (state && (page + 1) * 5 < state.season.levels) { page++; renderCurrent(); } };
    el('jump-current').onclick = function () { if (state) { page = Math.min(Math.floor(Math.max(0, state.level - 1) / 5), Math.ceil(state.season.levels / 5) - 1); renderCurrent(); } };
    el('claim-all').onclick = function () {
        if (!state || busy) return; var count = 0; for (var i = 0; i < state.rewards.length; i++) if (state.rewards[i].available) count++;
        openDialog('CLAIM EARNED REWARDS', 'Claim ' + count + ' rewards', '<p>All currently available rewards from your owned tracks will be delivered to Black Cloud mail.</p><p class="cost-row">Mailbox space needed <b>' + count + ' letters</b></p><p class="muted">No Kinah cost. Each reward can be claimed only once.</p>', { action: 'claimAll' }, 'Claim all ' + count, !count);
    };
    el('dialog-confirm').onclick = function () { if (modalAction) submit(modalAction, false); };
    el('dialog-close').onclick = closeDialog; el('dialog-cancel').onclick = closeDialog;
    el('retry').onclick = function () { if (retryAction) submit(retryAction, true); };
    document.addEventListener('keydown', function (e) {
        if (el('shade').className.indexOf('hidden') !== -1) return;
        if (e.keyCode === 27) closeDialog();
        if (e.keyCode === 9) { var nodes = el('shade').querySelectorAll('button:not(:disabled)'), first = nodes[0], last = nodes[nodes.length - 1]; if (e.shiftKey && document.activeElement === first) { last.focus(); e.preventDefault(); } else if (!e.shiftKey && document.activeElement === last) { first.focus(); e.preventDefault(); } }
    });
    load(true);
    setInterval(function () { timer(); if (state && view === 'missions') updateMissionReset(); }, 60000);
    setInterval(function () { if (!busy && el('shade').className.indexOf('hidden') !== -1) load(false); }, 30000);
})();
