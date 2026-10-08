package com.aionemu.gameserver.services;

import java.net.*;
import java.net.http.*;
import java.nio.file.*;
import java.util.*;
import com.sun.net.httpserver.HttpServer;

/** Run from game-server: verify actual production handlers serve the original artwork bytes. */
public final class SeasonPassMediaCheck {
	public static void main(String[] args) throws Exception {
		var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
		server.createContext("/market/pass",SeasonPassHttpService::handle); server.start();
		String base="http://127.0.0.1:"+server.getAddress().getPort();
		int checks=0;
		try(var client=HttpClient.newHttpClient()) {
			for(String file:List.of("pass.html","pass.css","pass.js","ascendant-dawn.png","aether-frame.png","aether-crest.png","ascendant-crest.png","pass-panel.png")) {
				String route=file.endsWith(".html")?"/market/pass":"/market/pass/media/"+file;
				var response=client.send(HttpRequest.newBuilder(URI.create(base+route)).GET().build(),HttpResponse.BodyHandlers.ofByteArray());
				if(response.statusCode()!=200 || !Arrays.equals(response.body(),Files.readAllBytes(Path.of("config/season-pass/media",file)))) throw new AssertionError(file+" bytes");
				String mime=file.endsWith(".png")?"image/png":file.endsWith(".html")?"text/html":file.endsWith(".css")?"text/css":"application/javascript";
				if(!response.headers().firstValue("Content-Type").orElse("").startsWith(mime)) throw new AssertionError(file+" MIME");
				checks++;
			}
			for(String route:List.of("/market/pass/media/unknown.png","/market/pass/media/season.properties","/market/pass/media/pass-panel.png/extra")) {
				if(client.send(HttpRequest.newBuilder(URI.create(base+route)).GET().build(),HttpResponse.BodyHandlers.discarding()).statusCode()!=404) throw new AssertionError("Unlisted media route");
				checks++;
			}
		} finally { server.stop(0); }
		System.out.println("OK: "+checks+" production media checks: exact bytes, image MIME types and explicit route whitelist.");
	}
}
