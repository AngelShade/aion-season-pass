package com.aionemu.gameserver.services;

import static com.aionemu.gameserver.services.CentralMarketService.*;
import static com.aionemu.gameserver.services.SeasonPassRules.*;

import java.nio.file.*;
import java.sql.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.ScheduledFuture;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.aionemu.commons.database.DatabaseFactory;
import com.aionemu.gameserver.GameServer;
import com.aionemu.gameserver.dao.InventoryDAO;
import com.aionemu.gameserver.dataholders.DataManager;
import com.aionemu.gameserver.model.gameobjects.*;
import com.aionemu.gameserver.model.gameobjects.Persistable.PersistentState;
import com.aionemu.gameserver.model.gameobjects.player.Player;
import com.aionemu.gameserver.model.items.storage.StorageType;
import com.aionemu.gameserver.model.templates.npc.NpcRating;
import com.aionemu.gameserver.network.aion.serverpackets.SM_MAIL_SERVICE;
import com.aionemu.gameserver.services.item.ItemFactory;
import com.aionemu.gameserver.services.item.ItemPacketService;
import com.aionemu.gameserver.services.item.ItemPacketService.ItemUpdateType;
import com.aionemu.gameserver.utils.PacketSendUtility;
import com.aionemu.gameserver.utils.ThreadPoolManager;
import com.aionemu.gameserver.utils.idfactory.IDFactory;
import com.aionemu.gameserver.world.World;

/** Character-owned pass. XP, purchases and reward mail are transactional and restart-safe. */
public final class SeasonPassService {

	private static final Logger log = LoggerFactory.getLogger(SeasonPassService.class);
	private static final Path ROOT = Path.of("config/season-pass");
	static Season season;
	static List<Mission> missions = List.of();
	static List<Reward> rewards = List.of();
	private static volatile boolean ready;
	private static ScheduledFuture<?> pulse;
	private SeasonPassService() {}

	static void start() throws Exception {
		load(ROOT);
		for (Reward r : rewards) {
			var t = DataManager.ITEM_DATA.getItemTemplate(r.item());
			if (t == null || !t.getName().equals(r.name()))
				throw new IllegalStateException("Invalid or restricted pass reward: " + r);
			validateRewardItem(r.item(),r.count());
			if(r.classBundle()!=ClassBundle.NONE) for(var pc:com.aionemu.gameserver.model.PlayerClass.values()) {
				int id=classBundleItem(r.classBundle(),pc.name()); if(id!=0) validateRewardItem(id,r.count());
			}
		}
		try (Connection c = DatabaseFactory.getConnection(); Statement s = c.createStatement()) {
			for (String sql : Files.readString(ROOT.resolve("schema.sql")).split(";")) if (!sql.isBlank()) s.execute(sql);
		}
		ready = true;
		pulse = ThreadPoolManager.getInstance().scheduleAtFixedRate(() -> {
			for (Player p : World.getInstance().getAllPlayers()) {
				// A character must spend a full minute on the same connection.
				Object current = p.getClientConnection();
				if (current == null) continue;
				long now=System.nanoTime(); Tick previous=online.get(p.getObjectId());
				if(previous==null || previous.connection()!=current) online.put(p.getObjectId(),new Tick(current,now));
				else if(p.isOnline() && now-previous.since()>=60_000_000_000L) {
					online.put(p.getObjectId(),new Tick(current,now));
					record(p,Event.MINUTE);
					record(p,Event.LOGIN); // still-online characters qualify when a new local day starts
				}
			}
			online.keySet().removeIf(id -> { Player p=World.getInstance().getPlayer(id); return p==null || !p.isOnline(); });
		}, 60000, 60000);
		log.info("Season pass {} ready: {} levels, {} missions, {} rewards", season.id(), season.levels(), missions.size(), rewards.size());
	}
	private record Tick(Object connection,long since) {}
	private static final Map<Integer,Tick> online = new java.util.concurrent.ConcurrentHashMap<>();
	static void stop() { ready = false; if (pulse != null) pulse.cancel(false); online.clear(); }
	private static void validateRewardItem(int id,long count) {
		var t=DataManager.ITEM_DATA.getItemTemplate(id);
		if(t==null || count>t.getMaxStackCount() || t.getExpireTime()!=0
			|| t.getRace()!=com.aionemu.gameserver.model.Race.PC_ALL
			|| t.getUseLimits()!=null && t.getUseLimits().getGenderPermitted()!=null)
			throw new IllegalStateException("Invalid or restricted pass item: "+id);
		if(t.getActions()!=null && t.getActions().getItemActions().stream().anyMatch(a->a instanceof com.aionemu.gameserver.model.templates.item.actions.DecomposeAction)) {
			var info=DataManager.DECOMPOSABLE_ITEMS_DATA.getInfoByItemId(id);
			var selectable=DataManager.DECOMPOSABLE_ITEMS_DATA.getSelectableItems(id);
			if((selectable==null || selectable.isEmpty()) && (info==null || info.isEmpty() || info.stream().anyMatch(g->g.getItems().isEmpty() && g.getRandomItems().isEmpty())))
				throw new IllegalStateException("Empty season pass reward box: "+id);
		}
	}
	private static boolean classReady(Reward r,Player p) {
		return r.classBundle()==ClassBundle.NONE || classBundleItem(r.classBundle(),p.getPlayerClass().name())!=0;
	}
	private static Reward resolve(Reward r,Player p) {
		if(r.classBundle()==ClassBundle.NONE) return r;
		int id=classBundleItem(r.classBundle(),p.getPlayerClass().name());
		if(id==0) return r; // preview placeholder only; claims are blocked until ascension
		return new Reward(r.level(),r.track(),id,r.count(),DataManager.ITEM_DATA.getItemTemplate(id).getName(),r.description(),r.classBundle());
	}
	/** Preview the existing native contents; selecting/rolling still happens in the game's own box window. */
	private static Map<String,Object> boxPreview(Reward r,Player p) {
		var info=DataManager.DECOMPOSABLE_ITEMS_DATA.getInfoByItemId(r.item());
		List<com.aionemu.gameserver.model.templates.item.ResultedItem> contents=new ArrayList<>();
		var selectable=DataManager.DECOMPOSABLE_ITEMS_DATA.getSelectableItems(r.item());
		boolean choice=selectable!=null;
		if(choice) for(var item:selectable) if(item.isObtainableFor(p)) contents.add(item);
		boolean random=false;
		if(info!=null) for(var group:info) if(p.getLevel()>=group.getMinLevel() && p.getLevel()<=group.getMaxLevel()) {
			random |= info.size()>1 || group.getChance()<100 || !group.getRandomItems().isEmpty();
			for(var item:group.getItems()) if(item.isObtainableFor(p)) contents.add(item);
		}
		List<Map<String,Object>> items=new ArrayList<>(); Set<Integer> seen=new HashSet<>();
		for(var item:contents) if(seen.add(item.getItemId())) {
			var t=DataManager.ITEM_DATA.getItemTemplate(item.getItemId());
			items.add(Map.of("item",item.getItemId(),"name",t.getName(),"min",item.getMinCount(),"max",item.getMaxCount(),"requiredLevel",t.getLevel()));
		}
		return Map.of("mode",choice?"choice":random?"random":"contents","items",items);
	}

	static void load(Path root) throws Exception {
		Properties p = new Properties(); try (var in = Files.newInputStream(root.resolve("season.properties"))) { p.load(in); }
		ZoneId zone = ZoneId.of(p.getProperty("timezone"));
		season = new Season(p.getProperty("id"), p.getProperty("serverName"), p.getProperty("name"), p.getProperty("subtitle"), zone,
			LocalDateTime.parse(p.getProperty("starts")).atZone(zone).toInstant(),
			LocalDateTime.parse(p.getProperty("ends")).atZone(zone).toInstant(),
			LocalDateTime.parse(p.getProperty("claimsEnd")).atZone(zone).toInstant(),
			Integer.parseInt(p.getProperty("levels")), Integer.parseInt(p.getProperty("xpPerLevel")),
			Long.parseLong(p.getProperty("premiumKinah")), Long.parseLong(p.getProperty("advancedKinah")), Integer.parseInt(p.getProperty("advancedLevels")));
		if (season.serverName() == null || season.serverName().isBlank() || !season.id().matches("[a-zA-Z0-9-]{1,40}") || season.levels() < 1 || season.levels() > 100 || season.xpPerLevel() < 1
			|| season.premiumKinah() < 1 || season.advancedKinah() <= season.premiumKinah() || season.advancedKinah() > 1_000_000_000_000L
			|| season.advancedLevels() < 0 || season.advancedLevels() > season.levels() || !season.ends().isAfter(season.starts())
			|| !season.claimsEnd().isAfter(season.ends())) throw new IllegalArgumentException("Invalid season settings.");
		season.maxXp();
		List<Mission> ms = new ArrayList<>(); Set<String> ids = new HashSet<>();
		for (String line : Files.readAllLines(root.resolve("missions.tsv"))) {
			if (line.isBlank() || line.startsWith("#")) continue;
			String[] f = line.split("\t",7);
			if (f.length != 7) throw new IllegalArgumentException("Invalid mission row.");
			Mission m = new Mission(f[0],Cadence.valueOf(f[1]),Event.valueOf(f[2]),Integer.parseInt(f[3]),Integer.parseInt(f[4]),f[5],f[6]);
			if (!m.id().matches("[a-z0-9-]{1,40}") || !ids.add(m.id()) || m.target() < 1 || m.xp() < 1 || m.xp() > season.maxXp())
				throw new IllegalArgumentException("Invalid mission: " + m.id());
			ms.add(m);
		}
		missions = List.copyOf(ms);
		List<Reward> rs = new ArrayList<>(); Set<String> slots = new HashSet<>();
		for (String line : Files.readAllLines(root.resolve("rewards.tsv"))) {
			if (line.isBlank() || line.startsWith("#")) continue;
			String[] f = line.split("\t",-1);
			if (f.length != 6 && f.length != 7) throw new IllegalArgumentException("Invalid reward row.");
			Reward r = new Reward(Integer.parseInt(f[0]),Integer.parseInt(f[1]),Integer.parseInt(f[2]),Long.parseLong(f[3]),f[4],f[5],f.length==7?ClassBundle.valueOf(f[6]):ClassBundle.NONE);
			if (r.level() < 1 || r.level() > season.levels() || r.track() < 0 || r.track() > 2 || r.count() < 1 || !slots.add(r.level()+":"+r.track()))
				throw new IllegalArgumentException("Invalid reward: " + r);
			if(r.classBundle()!=ClassBundle.NONE && r.item()!=classBundleItem(r.classBundle(),"GLADIATOR"))
				throw new IllegalArgumentException("Class bundle must specify its native base item: "+r);
			rs.add(r);
		}
		if (rs.size() != season.levels()*3 || ms.isEmpty()) throw new IllegalArgumentException("Every level needs all three reward tracks.");
		rewards = List.copyOf(rs);
	}

	static Map<String,Object> progress(Connection c, int player) throws SQLException {
		update(c,"INSERT IGNORE INTO season_pass_progress(season_id,player_id) VALUES(?,?)",season.id(),player);
		return row(c,"SELECT * FROM season_pass_progress WHERE season_id=? AND player_id=? FOR UPDATE",season.id(),player);
	}
	static boolean flag(Map<String,Object> row,String field) {
		Object value=row.get(field); return value instanceof Boolean b ? b : ((Number)value).intValue()!=0;
	}
	/** Caller locks the character's progress row before any mission/rival changes. */
	static int event(Connection c, int player, Event event, Instant now) throws SQLException {
		if (!season.active(now)) return 0;
		progress(c,player); int earned = 0;
		for (Mission m : missions) {
			if (m.event() != event) continue;
			String period = period(m,season,now);
			update(c,"INSERT IGNORE INTO season_pass_missions(season_id,player_id,mission_id,period_key) VALUES(?,?,?,?)",season.id(),player,m.id(),period);
			Map<String,Object> r = row(c,"SELECT progress,awarded FROM season_pass_missions WHERE season_id=? AND player_id=? AND mission_id=? AND period_key=?",season.id(),player,m.id(),period);
			if (flag(r,"awarded")) continue;
			int next = (int)Math.min(m.target(),lng(r,"progress")+1);
			boolean done = next == m.target();
			update(c,"UPDATE season_pass_missions SET progress=?,awarded=? WHERE season_id=? AND player_id=? AND mission_id=? AND period_key=?",next,done,season.id(),player,m.id(),period);
			if (done) earned += m.xp();
		}
		if (earned > 0) update(c,"UPDATE season_pass_progress SET xp=LEAST(?,xp+?) WHERE season_id=? AND player_id=?",season.maxXp(),earned,season.id(),player);
		return earned;
	}
	public static void record(Player p, Event event) {
		if (!ready || p == null || !season.active(Instant.now())) return;
		Object guard = p.getClientConnection(); if (guard == null) return;
		synchronized (guard) {
			if (p.getClientConnection() != guard || !p.isOnline()) return;
			try (Connection c = DatabaseFactory.getConnection()) {
				c.setAutoCommit(false);
				try { int earned = event(c,p.getObjectId(),event,Instant.now()); c.commit();
					if (earned > 0) PacketSendUtility.sendMessage(p,"Daeva Pass: mission complete! +"+earned+" Season XP. Open /seasonpass to claim rewards.");
				} catch (Exception e) { c.rollback(); throw e; }
			} catch (Exception e) { log.error("Could not record season mission {} for {}",event,p,e); }
		}
	}
	public static void onLogin(Player p) { if (p.getClientConnection()!=null) online.put(p.getObjectId(),new Tick(p.getClientConnection(),System.nanoTime())); record(p,Event.LOGIN); }
	public static void onNpcKill(Player p, Npc npc) {
		if (!ready || !season.active(Instant.now()) || npc.getLevel() < p.getLevel()-10 || npc.getObjectTemplate().isDialogNpc()
			|| !npc.getController().markSeasonPassCredit(p.getObjectId())) return;
		record(p,Event.HUNT);
		NpcRating rating = npc.getObjectTemplate().getRating();
		if (rating == NpcRating.ELITE || rating == NpcRating.HERO || rating == NpcRating.LEGENDARY) record(p,Event.ELITE);
	}
	public static void onPvpKill(Player p, Player victim) {
		if (!ready || p.getRace()==victim.getRace() || p.getAccount().getId()==victim.getAccount().getId()
			|| Math.abs(p.getLevel()-victim.getLevel()) > 10 || p.getClientConnection()==null) return;
		synchronized (p.getClientConnection()) {
			try (Connection c = DatabaseFactory.getConnection()) {
				c.setAutoCommit(false);
				try {
					Instant now=Instant.now(); progress(c,p.getObjectId());
					if (season.active(now) && rival(c,p.getObjectId(),victim.getObjectId(),now.toEpochMilli())) event(c,p.getObjectId(),Event.PVP,now);
					c.commit();
				} catch (Exception e) { c.rollback(); throw e; }
			} catch (Exception e) { log.error("Could not record season PvP kill",e); }
		}
	}
	static boolean rival(Connection c,int player,int victim,long now) throws SQLException {
		var prior = row(c,"SELECT credited_at FROM season_pass_rivals WHERE season_id=? AND player_id=? AND victim_id=?",season.id(),player,victim);
		if (prior!=null && now-lng(prior,"credited_at")<1800000) return false;
		update(c,"INSERT INTO season_pass_rivals VALUES(?,?,?,?) ON DUPLICATE KEY UPDATE credited_at=VALUES(credited_at)",season.id(),player,victim,now); return true;
	}

	static Upgrade purchase(Connection c,int player,int tier,int coin,long balance,Instant now) throws SQLException {
		var r=progress(c,player);
		Upgrade plan=upgrade(season,(int)lng(r,"tier"),tier,(int)lng(r,"xp"),flag(r,"boost_granted"),now);
		if (balance < plan.cost()) throw new IllegalArgumentException("Not enough Kinah in your character Inventory.");
		if (update(c,"UPDATE inventory SET item_count=item_count-? WHERE item_unique_id=? AND item_owner=? AND item_location=0 AND item_id=182400001 AND item_count=?",plan.cost(),coin,player,balance)!=1)
			throw new SQLException("Kinah changed. Refresh and try again.");
		update(c,"UPDATE season_pass_progress SET tier=?,xp=?,boost_granted=? WHERE season_id=? AND player_id=?",tier,plan.xp(),plan.boost(),season.id(),player);
		return plan;
	}
	static void receipt(Connection c,int player,String request,String action,String result) throws SQLException {
		update(c,"INSERT INTO season_pass_requests VALUES(?,?,?,?,?,?)",request,season.id(),player,action,result,System.currentTimeMillis());
	}
	static void claimRow(Connection c,int player,Reward r,int mail,Instant now) throws SQLException {
		var p=progress(c,player);
		boolean claimed=row(c,"SELECT 1 FROM season_pass_claims WHERE season_id=? AND player_id=? AND reward_level=? AND track=?",season.id(),player,r.level(),r.track())!=null;
		if (!canClaim(season,r,(int)lng(p,"tier"),(int)lng(p,"xp"),claimed,now)) throw new IllegalArgumentException("That reward is locked, already claimed, or outside the claim period.");
		update(c,"INSERT INTO season_pass_claims VALUES(?,?,?,?,?,?,?,?)",season.id(),player,r.level(),r.track(),mail,r.item(),r.count(),now.toEpochMilli());
	}
	static String mailTitle(Reward r) { return "Pass Lv."+r.level()+" "+(r.track()==0?"Free":r.track()==1?"Premium":"Advanced"); }
	static String mailMessage(Reward r) { return season.name()+": "+r.name()+" x"+r.count()+". "+r.description(); }
	static void saveReward(Connection c,int player,Reward r,int mail,int item,Instant now) throws SQLException {
		claimRow(c,player,r,mail,now);
		update(c,"INSERT INTO mail(mail_unique_id,mail_recipient_id,sender_name,mail_title,mail_message,unread,attached_item_id,attached_kinah_count,express) VALUES(?,?,'Daeva Pass',?,?,1,?,0,2)",mail,player,mailTitle(r),mailMessage(r),item);
	}
	public static String action(Player p, Map<String,String> args, String request) throws Exception {
		if (!ready) throw new IllegalStateException("Season pass is unavailable.");
		Object guard=p.getClientConnection(); if(guard==null) throw new IllegalArgumentException("Reopen the pass after logging in.");
		synchronized (guard) {
			if (p.getClientConnection()!=guard || World.getInstance().getPlayer(p.getObjectId())!=p || !p.isOnline() || p.isTrading() || p.isDead() || GameServer.isShuttingDownSoon())
				throw new IllegalArgumentException("Finish trading or reconnect before using the pass.");
			String action=args.getOrDefault("action","");
			if (!Set.of("purchase","claim","claimAll").contains(action)) throw new IllegalArgumentException("Unknown season pass action.");
			List<Integer> allocated=new ArrayList<>(); List<Letter> mail=new ArrayList<>(); boolean committed=false;
			Item coin=p.getInventory().getKinahItem(); long balance=p.getInventory().getKinah(); Upgrade plan=null;
			try (Connection c=DatabaseFactory.getConnection()) {
				c.setAutoCommit(false);
				try {
					var state=progress(c,p.getObjectId());
					var prior=row(c,"SELECT result,action FROM season_pass_requests WHERE request_id=? AND player_id=? AND season_id=?",request,p.getObjectId(),season.id());
					if (prior!=null) { if (!action.equals(str(prior,"action"))) throw new IllegalArgumentException("Refresh before making another selection."); return str(prior,"result"); }
					String result;
					if (action.equals("purchase")) {
						if (coin==null) throw new IllegalArgumentException("Not enough Kinah in Inventory.");
						if (!InventoryDAO.store(p)) throw new SQLException("Inventory save failed.");
						int tier=Integer.parseInt(args.getOrDefault("tier","0"));
						plan=purchase(c,p.getObjectId(),tier,coin.getObjectId(),balance,Instant.now());
						result=(tier==1?"Premium":"Advanced Premium")+" unlocked. Paid "+plan.cost()+" Kinah. Earlier earned rewards are now claimable.";
					} else {
						Instant now=Instant.now(); Set<String> claimed=new HashSet<>();
						for(var r:rows(c,"SELECT reward_level,track FROM season_pass_claims WHERE season_id=? AND player_id=?",season.id(),p.getObjectId())) claimed.add(lng(r,"reward_level")+":"+lng(r,"track"));
						List<Reward> selected=new ArrayList<>();
						for(Reward r:rewards) if (canClaim(season,r,(int)lng(state,"tier"),(int)lng(state,"xp"),claimed.contains(r.level()+":"+r.track()),now)
							&& classReady(r,p) && (action.equals("claimAll") || (Integer.toString(r.level()).equals(args.get("level")) && Integer.toString(r.track()).equals(args.get("track"))))) selected.add(resolve(r,p));
						if(selected.isEmpty()) throw new IllegalArgumentException("No eligible rewards to claim.");
						var mailboxCount=row(c,"SELECT COUNT(*) n FROM mail WHERE mail_recipient_id=?",p.getObjectId());
						if(lng(mailboxCount,"n")+selected.size()>200) throw new IllegalArgumentException("Collect existing mail first. These rewards need "+selected.size()+" free letters.");
						for(Reward r:selected) {
							Item item=ItemFactory.newItem(r.item(),r.count()); allocated.add(item.getObjectId()); item.setItemLocation(StorageType.MAILBOX.getId());
							if(!InventoryDAO.insertTransactionItem(c,item,p)) throw new SQLException("Reward item could not be saved.");
							int id=IDFactory.getInstance().nextId(); allocated.add(id);
							saveReward(c,p.getObjectId(),r,id,item.getObjectId(),now);
							mail.add(new Letter(id,p.getObjectId(),item,0,mailTitle(r),mailMessage(r),"Daeva Pass",new Timestamp(now.toEpochMilli()),true,LetterType.BLACKCLOUD));
						}
						update(c,"UPDATE players SET mailbox_letters=? WHERE id=?",lng(mailboxCount,"n")+mail.size(),p.getObjectId());
						result="Claimed "+mail.size()+" reward"+(mail.size()==1?"":"s")+". Collect them from Black Cloud mail.";
					}
					receipt(c,p.getObjectId(),request,action,result); c.commit(); committed=true;
					try {
						if(plan!=null) { coin.setItemCount(balance-plan.cost()); coin.setPersistentState(PersistentState.UPDATED);
							ItemPacketService.sendItemUpdatePacket(p,p.getInventory().getStorageType(),coin,ItemUpdateType.DEC_KINAH_BUY); }
						for(Letter l:mail) {
							l.setPersistentState(PersistentState.UPDATED);
							l.getAttachedItem().setPersistentState(PersistentState.UPDATED);
							p.getMailbox().putLetterToMailbox(l);
						}
						if(!mail.isEmpty()) { p.getCommonData().setMailboxLetters(p.getMailbox().size()); PacketSendUtility.sendPacket(p,new SM_MAIL_SERVICE()); }
					} catch(Exception refresh) {
						if(plan!=null) { coin.setItemCount(balance-plan.cost()); InventoryDAO.quarantineMarketInventory(p.getObjectId()); }
						log.error("Committed season pass action needs reconnect for {}",p,refresh); p.getClientConnection().close();
						return result+" Reconnect to refresh your Inventory and mail.";
					}
					log.info("Season pass {} for {}: {}",action,p,result); return result;
				} catch(Exception e) { if(!committed) { c.rollback(); for(int id:allocated) IDFactory.getInstance().releaseId(id); } throw e; }
			}
		}
	}
	public static Map<String,Object> snapshot(Player p) throws Exception {
		if(!ready) throw new IllegalStateException("Season pass is unavailable.");
		Object guard=p.getClientConnection(); if(guard==null) throw new IllegalArgumentException("Log in and reopen the pass.");
		synchronized(guard) {
			try(Connection c=DatabaseFactory.getConnection()) {
				c.setAutoCommit(false); Instant now=Instant.now(); var state=progress(c,p.getObjectId());
				Map<String,Object> out=new LinkedHashMap<>();
				out.put("season",season); out.put("now",now.toEpochMilli()); out.put("starts",season.starts().toEpochMilli()); out.put("ends",season.ends().toEpochMilli()); out.put("claimsEnd",season.claimsEnd().toEpochMilli());
				out.put("active",season.active(now)); out.put("claimable",season.claimable(now)); out.put("character",p.getName()); out.put("kinah",p.getInventory().getKinah());
				out.put("tier",lng(state,"tier")); out.put("xp",lng(state,"xp")); out.put("level",season.level((int)lng(state,"xp")));
				Map<String,Map<String,Object>> saved=new HashMap<>();
				for(var r:rows(c,"SELECT mission_id,period_key,progress,awarded FROM season_pass_missions WHERE season_id=? AND player_id=?",season.id(),p.getObjectId())) saved.put(str(r,"mission_id")+":"+str(r,"period_key"),r);
				// During the grace period, show the final day's/week's counters instead of a fresh reset.
				Instant missionTime=now.isBefore(season.ends())?now:season.ends().minusMillis(1);
				List<Map<String,Object>> ms=new ArrayList<>();
				for(Mission m:missions) {
					var r=saved.get(m.id()+":"+period(m,season,missionTime));
					ms.add(Map.of("id",m.id(),"cadence",m.cadence(),"name",m.name(),"description",m.description(),"target",m.target(),"xp",m.xp(),"progress",r==null?0:lng(r,"progress"),"complete",r!=null&&flag(r,"awarded"),"reset",reset(m,season,missionTime).toEpochMilli()));
				}
				out.put("missions",ms); Set<String> claimed=new HashSet<>();
				List<Map<String,Object>> history=rows(c,"SELECT reward_level,track,item_id,quantity,claimed_at FROM season_pass_claims WHERE season_id=? AND player_id=? ORDER BY claimed_at DESC",season.id(),p.getObjectId());
				for(var r:history) claimed.add(lng(r,"reward_level")+":"+lng(r,"track"));
				out.put("history",history); List<Map<String,Object>> rs=new ArrayList<>();
				for(Reward configured:rewards) {
					Reward r=resolve(configured,p); boolean needsClass=!classReady(configured,p);
					boolean done=claimed.contains(r.level()+":"+r.track()); var t=DataManager.ITEM_DATA.getItemTemplate(r.item());
					Map<String,Object> entry=new LinkedHashMap<>();
					entry.putAll(Map.of("level",r.level(),"track",r.track(),"item",r.item(),"quantity",r.count(),"name",needsClass?"Class Stigma Bundle":r.name(),"description",r.description(),"requiredLevel",t.getLevel(),"claimed",done,"available",!needsClass&&canClaim(season,r,(int)lng(state,"tier"),(int)lng(state,"xp"),done,now)));
					entry.put("needsClass",needsClass); entry.put("box",needsClass?Map.of("mode","contents","items",List.of()):boxPreview(r,p)); rs.add(entry);
				}
				out.put("rewards",rs); c.commit(); return out;
			}
		}
	}
}
