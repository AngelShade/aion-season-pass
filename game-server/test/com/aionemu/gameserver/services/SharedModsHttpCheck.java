package com.aionemu.gameserver.services;
import java.net.*;
import java.net.http.*;
import java.nio.file.*;
import java.util.*;
import com.sun.net.httpserver.HttpServer;
/** Exercise all production routes on one isolated loopback socket, without GameServer startup. */
public final class SharedModsHttpCheck {
    public static void main(String[] args) throws Exception {
        com.aionemu.gameserver.configs.main.CustomConfig.ENABLE_POETA_JOURNEY = true;
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        SharedModsHttpService.routes(server);server.start();int checks=0;
        try(var client=HttpClient.newHttpClient()) {
            String base="http://127.0.0.1:"+server.getAddress().getPort();
            for(String[] route:new String[][]{{"/market","config/central-market/media/market.html"},{"/market/wardrobe","config/wardrobe/media/wardrobe.html"},{"/market/pass","config/season-pass/media/pass.html"},{"/journey","config/journey/media/journey.html"}}) {
                var response=client.send(HttpRequest.newBuilder(URI.create(base+route[0])).GET().build(),HttpResponse.BodyHandlers.ofByteArray());
                if(response.statusCode()!=200 || !Arrays.equals(response.body(),Files.readAllBytes(Path.of(route[1]))))throw new AssertionError(route[0]);checks++;
                response=client.send(HttpRequest.newBuilder(URI.create(base+route[0]+"/state")).GET().build(),HttpResponse.BodyHandlers.ofByteArray());
                if(response.statusCode()!=403)throw new AssertionError("Anonymous state: "+route[0]);checks++;
                response=client.send(HttpRequest.newBuilder(URI.create(base+route[0]+"/action")).POST(HttpRequest.BodyPublishers.ofString("action=claim")).build(),HttpResponse.BodyHandlers.ofByteArray());
                if(response.statusCode()!=403)throw new AssertionError("Anonymous action: "+route[0]);checks++;
            }
            for(String origin:List.of("https://play.example.com","https://play.example.com:8443","http://127.0.0.1:8091")) {
                if(!SeasonPassHttpService.matchesOriginHost(origin,URI.create(origin).getRawAuthority()))throw new AssertionError("Origin support");checks++;
            }
            for(String origin:List.of("https://evil.example","https://play.example.com/extra","https://user@play.example.com","null")) {
                if(SeasonPassHttpService.matchesOriginHost(origin,"play.example.com"))throw new AssertionError("Origin rejection");checks++;
            }
        } finally {server.stop(0);}
        System.out.println("OK: "+checks+" shared-listener production routing/authentication and HTTPS origin checks; GameServer never started.");
    }
}
