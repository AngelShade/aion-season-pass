package com.aionemu.gameserver.services;

import java.io.IOException;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.SecureRandom;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import com.alibaba.fastjson2.JSON;
import com.aionemu.gameserver.model.gameobjects.player.Player;
import com.sun.net.httpserver.HttpExchange;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Embedded-browser API: online session + connection-bound form for every mutation. */
public final class SeasonPassHttpService {
	private static final Logger log=LoggerFactory.getLogger(SeasonPassHttpService.class);
	private static final Path MEDIA=Path.of("config/season-pass/media");
	private static final SecureRandom RANDOM=new SecureRandom();
	private static final Map<String,Form> FORMS=new ConcurrentHashMap<>();
	private record Form(Player player,Object connection,long expires) {}
	private SeasonPassHttpService() {}

    private static com.sun.net.httpserver.HttpServer listener;
    public static synchronized void start() throws Exception {
        Properties settings = new Properties();
        try (var in = Files.newInputStream(Path.of("config/season-pass/season.properties"))) { settings.load(in); }
        if (!Boolean.parseBoolean(settings.getProperty("http.enabled", "true"))) return;
        if (listener != null) throw new IllegalStateException("Season Pass listener already started");
        String bind = settings.getProperty("http.bind", "127.0.0.1");
        int port = Integer.parseInt(settings.getProperty("http.port", "8091"));
        if (!java.net.InetAddress.getByName(bind).isLoopbackAddress())
            throw new IllegalArgumentException("Season Pass HTTP must bind to loopback; expose it through HTTPS");
        var server = com.sun.net.httpserver.HttpServer.create(new java.net.InetSocketAddress(bind, port), 16);
        try {
            SeasonPassService.start();
            server.createContext("/market/pass", SeasonPassHttpService::handle);
            server.setExecutor(com.aionemu.gameserver.utils.ThreadPoolManager.getInstance());
            server.start(); listener = server;
            log.info("Season Pass HTTP listening at http://{}:{}/market/pass", bind, port);
        } catch (Exception e) { server.stop(0); SeasonPassService.stop(); throw e; }
    }
    public static synchronized void stop() {
        if (listener != null) { listener.stop(1); listener = null; }
        FORMS.clear(); SeasonPassService.stop();
    }
    static Player findPlayer(String sessionId) {
        if (sessionId == null || sessionId.isBlank() || sessionId.length() > 256) return null;
        byte[] supplied = sessionId.getBytes(StandardCharsets.US_ASCII);
        for (Player player : com.aionemu.gameserver.world.World.getInstance().getAllPlayers()) {
            if (!player.isOnline() || player.getClientConnection() == null) continue;
            String token = player.getAccount().getSecurityToken();
            if (token == null || token.length() < 16) continue;
            byte[] full = token.getBytes(StandardCharsets.US_ASCII);
            byte[] prefix = java.util.HexFormat.of().formatHex(token.substring(0, 16).getBytes(StandardCharsets.US_ASCII)).getBytes(StandardCharsets.US_ASCII);
            if (java.security.MessageDigest.isEqual(supplied, full) || java.security.MessageDigest.isEqual(supplied, prefix)) return player;
        }
        return null;
    }

	public static void handle(HttpExchange x) throws IOException {
		try {
			x.getResponseHeaders().set("Cache-Control","no-store");
			x.getResponseHeaders().set("X-Content-Type-Options","nosniff");
			x.getResponseHeaders().set("Referrer-Policy","no-referrer");
			String path=x.getRequestURI().getPath(), method=x.getRequestMethod();
			if(method.equals("GET") && (path.equals("/market/pass") || path.matches("/market/pass/media/(pass\\.(css|js)|(ascendant-dawn|aether-frame|aether-crest|ascendant-crest|pass-panel)\\.png)"))) {
				String file=path.equals("/market/pass")?"pass.html":path.substring(path.lastIndexOf('/')+1);
				if(file.endsWith(".png")) {
					byte[] bytes=Files.readAllBytes(MEDIA.resolve(file)); x.getResponseHeaders().set("Content-Type","image/png");
					x.sendResponseHeaders(200,bytes.length); x.getResponseBody().write(bytes);
				} else send(x,200,file.endsWith(".html")?"text/html":file.endsWith(".css")?"text/css":"application/javascript",Files.readString(MEDIA.resolve(file)));
				return;
			}
			boolean action=path.equals("/market/pass/action");
			if(!action && !path.equals("/market/pass/state")) { send(x,404,"text/plain","Not found"); return; }
			if(!method.equals(action?"POST":"GET")) { send(x,405,"application/json","{\"error\":\"Method not allowed.\"}"); return; }
			Map<String,String> args=parse(action?new String(x.getRequestBody().readNBytes(8193),StandardCharsets.UTF_8):x.getRequestURI().getRawQuery());
			Player p=findPlayer(args.getOrDefault("session_id",""));
			if(p==null || !p.isOnline()) { send(x,403,"application/json","{\"error\":\"Log in and reopen Season Pass from Additional Functions.\"}"); return; }
			String notice="";
			if(action) {
				String origin=x.getRequestHeaders().getFirst("Origin"), host=x.getRequestHeaders().getFirst("Host");
				if(origin!=null && !matchesOriginHost(origin,host)) throw new IllegalArgumentException("Reopen the pass to continue.");
				Form form=FORMS.get(args.getOrDefault("request",""));
				if(form==null || form.player()!=p || form.connection()!=p.getClientConnection() || form.expires()<System.currentTimeMillis()) {
					send(x,403,"application/json","{\"error\":\"This selection expired. Refresh the pass.\"}"); return;
				}
				notice=SeasonPassService.action(p,args,args.get("request"));
			}
			var state=SeasonPassService.snapshot(p);
			long now=System.currentTimeMillis(); FORMS.entrySet().removeIf(e->e.getValue().expires()<now);
			if(FORMS.size()>=5000) throw new IllegalStateException("Season Pass is busy.");
			byte[] bytes=new byte[24]; RANDOM.nextBytes(bytes); String id=Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
			FORMS.put(id,new Form(p,p.getClientConnection(),now+600000)); state.put("request",id); state.put("notice",notice);
			send(x,200,"application/json",JSON.toJSONString(state));
		} catch(IllegalArgumentException e) { send(x,400,"application/json",JSON.toJSONString(Map.of("error",e.getMessage()))); }
		catch(Exception e) { log.error("Season Pass request failed",e); send(x,503,"application/json","{\"error\":\"Season Pass is unavailable. Refresh before trying again.\"}"); }
		finally { x.close(); }
	}
	static Map<String,String> parse(String text) {
		if(text==null) return new HashMap<>();
		if(text.length()>8192) throw new IllegalArgumentException("Request is too large.");
		Map<String,String> out=new HashMap<>();
		for(String part:text.split("&")) { String[] kv=part.split("=",2); if(kv.length==2) out.put(URLDecoder.decode(kv[0],StandardCharsets.UTF_8),URLDecoder.decode(kv[1],StandardCharsets.UTF_8)); }
		return out;
	}
	private static boolean matchesOriginHost(String origin,String host) {
		try {
			URI uri=URI.create(origin);
			return host!=null && uri.getUserInfo()==null && "".equals(uri.getRawPath()) && uri.getQuery()==null && uri.getFragment()==null
				&& ("http".equals(uri.getScheme()) || "https".equals(uri.getScheme()))
				&& uri.getRawAuthority()!=null && uri.getRawAuthority().equalsIgnoreCase(host);
		} catch (IllegalArgumentException e) { return false; }
	}
	private static void send(HttpExchange x,int status,String type,String body) throws IOException {
		byte[] bytes=body.getBytes(StandardCharsets.UTF_8); x.getResponseHeaders().set("Content-Type",type+"; charset=utf-8");
		x.sendResponseHeaders(status,bytes.length); x.getResponseBody().write(bytes);
	}
}
