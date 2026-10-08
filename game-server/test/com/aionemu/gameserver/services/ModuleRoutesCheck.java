package com.aionemu.gameserver.services;

import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.*;
import com.sun.net.httpserver.HttpServer;
import com.aionemu.gameserver.configs.main.CustomConfig;

/** Every selectable browser combination, without database or GameServer initialization. */
public final class ModuleRoutesCheck {
    public static void main(String[] args) throws Exception {
        int checks = 0;
        try (var client = HttpClient.newHttpClient()) {
            for (int mask = 0; mask < 16; mask++) {
                CustomConfig.SHARED_MODS_MARKET = (mask & 1) != 0;
                CustomConfig.SHARED_MODS_WARDROBE = (mask & 2) != 0;
                CustomConfig.SHARED_MODS_PASS = (mask & 4) != 0;
                CustomConfig.ENABLE_POETA_JOURNEY = (mask & 8) != 0;
                var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
                SharedModsHttpService.routes(server);
                server.start();
                try {
                    String base = "http://127.0.0.1:" + server.getAddress().getPort();
                    String[] routes = {"/market", "/market/wardrobe", "/market/pass", "/journey"};
                    for (int index = 0; index < routes.length; index++) {
                        boolean enabled = (mask & (1 << index)) != 0;
                        for (String suffix : new String[]{"", "/state", "/action"}) {
                            var builder = HttpRequest.newBuilder(URI.create(base + routes[index] + suffix));
                            if (suffix.equals("/action")) builder.POST(HttpRequest.BodyPublishers.ofString("action=claim"));
                            else builder.GET();
                            var response = client.send(builder.build(), HttpResponse.BodyHandlers.ofByteArray());
                            int expected = !enabled ? 404 : suffix.isEmpty() ? 200 : 403;
                            if (response.statusCode() != expected)
                                throw new AssertionError("mask=" + mask + " route=" + routes[index] + suffix + " status=" + response.statusCode());
                            checks++;
                        }
                    }
                } finally { server.stop(0); }
            }
        }
        System.out.println("OK: " + checks + " production route/auth checks across all 16 browser combinations; no GameServer or DB startup.");
    }
}
