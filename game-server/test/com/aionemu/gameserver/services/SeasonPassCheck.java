package com.aionemu.gameserver.services;

import static com.aionemu.gameserver.services.SeasonPassRules.*;
import static com.aionemu.gameserver.services.CentralMarketService.*;
import java.nio.file.*;
import java.sql.*;
import java.time.*;
import java.util.*;
import javax.xml.stream.*;
import com.alibaba.fastjson2.JSON;

/** Deterministic rules/catalog checks; optional real MariaDB checks in a new, empty schema only. */
public final class SeasonPassCheck {
	private static int checks;
	private static void check(boolean ok,String name) { checks++; if(!ok) throw new AssertionError(name); }
	private static void refused(Runnable r,String name) { boolean ok=false; try { r.run(); } catch(IllegalArgumentException e) { ok=true; } check(ok,name); }
	private static long value(Connection c,String sql,Object... args) throws SQLException { return lng(row(c,sql,args),"n"); }
	private static final Instant NOW=Instant.parse("2026-10-03T10:00:00Z");
	public static void main(String[] args) throws Exception {
		SeasonPassService.load(Path.of("game-server/config/season-pass"));
		Season s=SeasonPassService.season;
		check(s.active(s.starts())&&!s.active(s.starts().minusMillis(1))&&!s.active(s.ends()),"season boundaries are start-inclusive and end-exclusive");
		check(s.claimable(s.ends())&&!s.claimable(s.claimsEnd()),"grace period permits claims until its exclusive deadline");
		check(s.level(999)==0&&s.level(1000)==1&&s.level(999999)==30,"level boundaries and cap");
		Upgrade premium=upgrade(s,0,1,2500,false,NOW);
		check(premium.cost()==1500000&&premium.xp()==2500&&!premium.boost(),"Premium preserves XP");
		Upgrade advanced=upgrade(s,0,2,2500,false,NOW), upgraded=upgrade(s,1,2,2500,false,NOW);
		check(advanced.cost()==3000000&&advanced.xp()==12500&&advanced.boost(),"Advanced grants ten levels");
		check(upgraded.cost()==1500000&&upgraded.xp()==advanced.xp(),"Premium to Advanced charges only the difference");
		check(upgrade(s,1,2,29500,false,NOW).xp()==30000,"boost stops at final level");
		check(upgrade(s,1,2,2500,true,NOW).xp()==2500,"boost never repeats");
		refused(()->upgrade(s,2,1,0,true,NOW),"downgrade refused");
		refused(()->upgrade(s,1,1,0,false,NOW),"duplicate purchase refused");
		refused(()->upgrade(s,0,3,0,false,NOW),"invalid tier refused");
		refused(()->upgrade(s,0,1,0,false,s.ends()),"expired purchase refused");
		Reward free=SeasonPassService.rewards.get(0), paid=SeasonPassService.rewards.get(1);
		check(canClaim(s,free,0,1000,false,NOW)&&!canClaim(s,paid,0,1000,false,NOW),"free and premium ownership gates");
		check(!canClaim(s,free,0,0,false,NOW)&&!canClaim(s,free,0,1000,true,NOW),"unearned and duplicate claims refused");
		check(canClaim(s,paid,2,1000,false,s.ends())&&!canClaim(s,paid,2,1000,false,s.claimsEnd()),"retroactive paid claims and grace deadline");
		Mission daily=SeasonPassService.missions.getFirst(), weekly=SeasonPassService.missions.stream().filter(m->m.cadence()==Cadence.WEEKLY).findFirst().orElseThrow();
		check(period(daily,s,Instant.parse("2026-10-03T21:01:00Z")).equals("2026-10-04"),"Bucharest midnight resets independently of UTC");
		check(period(weekly,s,NOW).equals("2026-09-28")&&period(weekly,s,Instant.parse("2026-10-04T21:01:00Z")).equals("2026-10-05"),"weekly resets on local Monday");
		Instant dst=Instant.parse("2026-10-24T21:00:00Z");
		check(Duration.between(dst,reset(daily,s,dst)).toHours()==25,"DST autumn day spans 25 hours");
		check(reset(weekly,s,s.ends().minusSeconds(1)).equals(s.ends()),"mission resets cannot extend the season");
		check(JSON.parseObject(JSON.toJSONString(s)).getIntValue("levels")==30,"record serializes for browser");
		refused(()->SeasonPassHttpService.parse("x".repeat(8193)),"oversize HTTP input refused");
		check(SeasonPassHttpService.parse("session_id=a%2Bb&action=claim").get("session_id").equals("a+b"),"session URL decoding");
		catalog();
		http();
		if(args.length>0) database(Path.of(args[0]));
		System.out.println("OK: "+checks+" season pass checks"+(args.length>0?" including isolated MariaDB transactions":"; database checks not requested")+". No live character data changed.");
	}
	private static void http() throws Exception {
		var server=com.sun.net.httpserver.HttpServer.create(new java.net.InetSocketAddress("127.0.0.1",0),0);
		server.createContext("/market/pass",SeasonPassHttpService::handle); server.start();
		String base="http://127.0.0.1:"+server.getAddress().getPort();
		try {
			var client=java.net.http.HttpClient.newHttpClient();
			for(String path:List.of("/market/pass/state","/market/pass/state?session_id=")) {
				var response=client.send(java.net.http.HttpRequest.newBuilder(java.net.URI.create(base+path)).GET().build(),java.net.http.HttpResponse.BodyHandlers.ofString());
				check(response.statusCode()==403,"anonymous and empty sessions cannot read character state");
			}
			var post=client.send(java.net.http.HttpRequest.newBuilder(java.net.URI.create(base+"/market/pass/action")).POST(java.net.http.HttpRequest.BodyPublishers.ofString("action=purchase&tier=2")).build(),java.net.http.HttpResponse.BodyHandlers.ofString());
			check(post.statusCode()==403,"anonymous purchase cannot mutate state");
			var wrongMethod=client.send(java.net.http.HttpRequest.newBuilder(java.net.URI.create(base+"/market/pass/action")).GET().build(),java.net.http.HttpResponse.BodyHandlers.ofString());
			check(wrongMethod.statusCode()==405,"GET cannot claim or purchase");
		} finally { server.stop(0); }
	}
	private static void catalog() throws Exception {
		Map<Integer,Map<String,String>> items=new HashMap<>();
		try(var in=Files.newInputStream(Path.of("game-server/data/static_data/items/item_templates.xml"))) {
			var r=XMLInputFactory.newFactory().createXMLStreamReader(in);
			while(r.hasNext()) if(r.next()==XMLStreamConstants.START_ELEMENT && r.getLocalName().equals("item_template")) {
				Map<String,String> a=new HashMap<>(); for(int i=0;i<r.getAttributeCount();i++) a.put(r.getAttributeLocalName(i),r.getAttributeValue(i)); items.put(Integer.parseInt(a.get("id")),a);
			} r.close();
		}
		Set<Integer> client=new HashSet<>();
		for(String line:Files.readAllLines(Path.of("game-server/config/central-market/media/icon_sources.tsv"))) { String[] f=line.split("\t"); if(f[0].matches("[0-9]{9}")) client.add(Integer.parseInt(f[0])); }
		for(Reward r:SeasonPassService.rewards) {
			var t=items.get(r.item()); check(t!=null&&t.get("name").equals(r.name()),"reward name matches actual template");
			check(r.count()<=Long.parseLong(t.getOrDefault("max_stack_count","1")),"reward fits native stack");
			check(client.contains(r.item()),"reward icon exists in matching client metadata");
			check(SeasonPassService.mailTitle(r).length()<=20&&SeasonPassService.mailMessage(r).length()<=1000,"mail fits legacy limits");
			check(r.item()/1000000!=162 && !r.name().contains("Dye"),"no serum or dye filler");
		}
		String[] classes={"GLADIATOR","TEMPLAR","ASSASSIN","RANGER","SORCERER","SPIRIT_MASTER","CLERIC","CHANTER","GUNNER","RIDER","BARD"};
		for(ClassBundle b:List.of(ClassBundle.NORMAL,ClassBundle.GREATER,ClassBundle.MAJOR)) {
			int base=b==ClassBundle.NORMAL?188053750:b==ClassBundle.GREATER?188053761:188053772;
			for(int i=0;i<classes.length;i++) {
				int id=classBundleItem(b,classes[i]);
				check(id==base+i && items.containsKey(id) && client.contains(id),"class reward resolves to native "+classes[i]+" "+b+" box");
			}
			for(String c:List.of("WARRIOR","SCOUT","MAGE","PRIEST","ENGINEER","ARTIST","invalid")) check(classBundleItem(b,c)==0,"base class cannot receive arbitrary stigma reward");
		}
		check(classBundleItem(ClassBundle.NONE,"BARD")==0,"ordinary rewards do not remap by class");
		int daily=SeasonPassService.missions.stream().filter(m->m.cadence()==Cadence.DAILY&&m.event()!=Event.PVP).mapToInt(Mission::xp).sum();
		check(daily*30>=SeasonPassService.season.maxXp(),"PvE daily missions alone can finish in 30 days");
	}
	private static void database(Path deployment) throws Exception {
		Properties p=new Properties(); try(var in=Files.newInputStream(deployment.resolve("config/network/database.properties"))) { p.load(in); }
		if(Files.exists(deployment.resolve("config/mygs.properties"))) try(var in=Files.newInputStream(deployment.resolve("config/mygs.properties"))) { p.load(in); }
		String url=p.getProperty("database.url").replace("${gameserver.timezone}","UTC"), user=p.getProperty("database.user"), password=p.getProperty("database.password");
		String schema="aion_pass_check_"+System.currentTimeMillis();
		try(Connection live=DriverManager.getConnection(url,user,password); Statement ddl=live.createStatement()) {
			String source=live.getCatalog(); check(source.matches("[A-Za-z0-9_]+")&&!source.equals(schema),"test schema is separate from live database");
			ddl.execute("CREATE DATABASE `"+schema+"`");
			try {
				ddl.execute("CREATE TABLE `"+schema+"`.inventory LIKE `"+source+"`.inventory");
				// Copy mail fields, omitting live-player foreign keys; no player/mail data are copied.
				ddl.execute("CREATE TABLE `"+schema+"`.mail LIKE `"+source+"`.mail");
				try(Connection c=DriverManager.getConnection(url.replace("/"+source,"/"+schema),user,password); Statement s=c.createStatement()) {
					check(c.getCatalog().equals(schema),"all test writes use isolated schema");
					for(String sql:Files.readString(Path.of("game-server/config/season-pass/schema.sql")).split(";")) if(!sql.isBlank()) s.execute(sql);
					c.setAutoCommit(false); SeasonPassService.progress(c,101); c.commit();
					SeasonPassService.event(c,101,Event.LOGIN,NOW); c.commit();
					check(value(c,"SELECT xp n FROM season_pass_progress WHERE player_id=101")==150,"login awards XP automatically");
					SeasonPassService.event(c,101,Event.LOGIN,NOW); c.commit();
					check(value(c,"SELECT xp n FROM season_pass_progress WHERE player_id=101")==150,"reconnect cannot repeat daily XP");
					SeasonPassService.event(c,101,Event.LOGIN,NOW.plusSeconds(86400)); c.commit();
					check(value(c,"SELECT xp n FROM season_pass_progress WHERE player_id=101")==300,"next local day can earn login XP");
					for(int i=0;i<30;i++) SeasonPassService.event(c,101,Event.HUNT,NOW); c.commit();
					check(value(c,"SELECT xp n FROM season_pass_progress WHERE player_id=101")==550,"hunt completion grants daily XP once");
					SeasonPassService.event(c,102,Event.LOGIN,NOW); c.commit();
					check(value(c,"SELECT xp n FROM season_pass_progress WHERE player_id=102")==150,"characters own separate progress");
					check(SeasonPassService.rival(c,101,102,NOW.toEpochMilli())&&!SeasonPassService.rival(c,101,102,NOW.toEpochMilli()+1799999)&&SeasonPassService.rival(c,101,102,NOW.toEpochMilli()+1800000),"PvP victim cooldown persists"); c.commit();
					update(c,"INSERT INTO inventory(item_unique_id,item_id,item_count,item_owner,item_location) VALUES(1001,182400001,4000000,101,0)"); c.commit();
					var bought=SeasonPassService.purchase(c,101,1,1001,4000000,NOW); c.commit();
					check(bought.cost()==1500000&&value(c,"SELECT item_count n FROM inventory WHERE item_unique_id=1001")==2500000&&value(c,"SELECT tier n FROM season_pass_progress WHERE player_id=101")==1,"Kinah debit and entitlement commit together");
					SeasonPassService.purchase(c,101,2,1001,2500000,NOW); c.rollback();
					check(value(c,"SELECT item_count n FROM inventory WHERE item_unique_id=1001")==2500000&&value(c,"SELECT tier n FROM season_pass_progress WHERE player_id=101")==1,"failed upgrade rolls back both debit and entitlement"); c.commit();
					SeasonPassService.purchase(c,101,2,1001,2500000,NOW); c.commit();
					check(value(c,"SELECT item_count n FROM inventory WHERE item_unique_id=1001")==1000000&&value(c,"SELECT xp n FROM season_pass_progress WHERE player_id=101")==10550,"Advanced upgrade persists differential price and exact boost");
					boolean invalid=false; try {SeasonPassService.purchase(c,102,1,1001,1000000,NOW);} catch(IllegalArgumentException|SQLException e){invalid=true;c.rollback();} check(invalid,"foreign coin or insufficient balance cannot buy");
					Reward reward=SeasonPassService.rewards.get(0);
					update(c,"INSERT INTO inventory(item_unique_id,item_id,item_count,item_owner,item_location) VALUES(1002,?,?,101,127)",reward.item(),reward.count());
					SeasonPassService.saveReward(c,101,reward,2001,1002,NOW); c.rollback();
					check(value(c,"SELECT COUNT(*) n FROM season_pass_claims")==0&&value(c,"SELECT COUNT(*) n FROM mail")==0&&value(c,"SELECT COUNT(*) n FROM inventory WHERE item_unique_id=1002")==0,"claim failure rolls back receipt, mail and item together");
					update(c,"INSERT INTO inventory(item_unique_id,item_id,item_count,item_owner,item_location) VALUES(1002,?,?,101,127)",reward.item(),reward.count());
					SeasonPassService.saveReward(c,101,reward,2001,1002,NOW); SeasonPassService.receipt(c,101,"request-a","claim","Claimed"); c.commit();
					check(value(c,"SELECT COUNT(*) n FROM mail m JOIN inventory i ON i.item_unique_id=m.attached_item_id WHERE m.mail_unique_id=2001 AND i.item_id=? AND i.item_count=?",reward.item(),reward.count())==1,"reward has one real persisted mail attachment");
					check(row(c,"SELECT result FROM season_pass_requests WHERE request_id='request-a' AND player_id=101").get("result").equals("Claimed"),"retry receipt survives reconnect");
					invalid=false; try {SeasonPassService.saveReward(c,101,reward,2002,1002,NOW);} catch(IllegalArgumentException e){invalid=true;c.rollback();} check(invalid&&value(c,"SELECT COUNT(*) n FROM mail")==1,"duplicate reward cannot create second mail");
					invalid=false; try {SeasonPassService.saveReward(c,102,SeasonPassService.rewards.get(1),2003,1002,NOW);} catch(IllegalArgumentException e){invalid=true;c.rollback();} check(invalid,"unowned/unearned reward cannot be mailed");
					update(c,"UPDATE season_pass_progress SET xp=29999 WHERE player_id=101"); SeasonPassService.event(c,101,Event.LOGIN,NOW.plusSeconds(172800)); c.commit();
					check(value(c,"SELECT xp n FROM season_pass_progress WHERE player_id=101")==30000,"mission XP stops at level cap");
					SeasonPassService.event(c,101,Event.LOGIN,SeasonPassService.season.ends()); c.commit();
					check(value(c,"SELECT COUNT(*) n FROM season_pass_missions WHERE player_id=101 AND mission_id='d-login'")==3,"expired season does not create progress");
				}
			} finally { ddl.execute("DROP DATABASE `"+schema+"`"); }
		}
	}
}
