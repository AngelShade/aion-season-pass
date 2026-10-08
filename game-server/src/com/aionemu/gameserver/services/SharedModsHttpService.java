package com.aionemu.gameserver.services;

import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Properties;
import com.sun.net.httpserver.HttpServer;
import com.aionemu.gameserver.configs.main.CustomConfig;
import com.aionemu.gameserver.utils.ThreadPoolManager;
import org.slf4j.LoggerFactory;

/** One private listener for the five published mods; HTTPS is terminated by the operator's proxy. */
public final class SharedModsHttpService {
    private static HttpServer listener;
    private SharedModsHttpService() {}
    static void routes(HttpServer server) {
        server.createContext("/market", CentralMarketHttpService::handle);
        server.createContext("/market/wardrobe", WardrobeHttpService::handle);
        server.createContext("/market/pass", SeasonPassHttpService::handle);
        server.createContext("/journey", PoetaJourneyHttpService::handle);
    }
    public static synchronized void start() throws Exception {
        if (listener != null) throw new IllegalStateException("Shared mod listener already started");
        if (!CustomConfig.UNIFIED_INVENTORY || !CustomConfig.EXPANDED_WAREHOUSES || !CustomConfig.ENABLE_POETA_JOURNEY)
            throw new IllegalStateException("Enable the matching shared Inventory/Warehouse and Journey server settings");
        for (String name : new String[]{"poeta.jpg", "sanctum.jpg", "ishalgen.jpg", "pandaemonium.jpg"})
            if (!Files.isRegularFile(Path.of("config/journey/media", name)))
                throw new IllegalStateException("Copy the combined client builder's Journey artwork to config/journey/media: " + name);
        Properties settings = new Properties();
        try (var input = Files.newInputStream(Path.of("config/season-pass/season.properties"))) { settings.load(input); }
        String bind = settings.getProperty("http.bind", "127.0.0.1");
        int port = Integer.parseInt(settings.getProperty("http.port", "8091"));
        if (!InetAddress.getByName(bind).isLoopbackAddress()) throw new IllegalArgumentException("Bind the shared listener to loopback behind HTTPS");
        HttpServer server = HttpServer.create(new InetSocketAddress(bind, port), 16);
        try {
            CentralMarketService.start();
            WardrobeService.start();
            PoetaJourneyService.start();
            SeasonPassService.start();
            routes(server);
            server.setExecutor(ThreadPoolManager.getInstance());
            server.start(); listener = server;
            LoggerFactory.getLogger(SharedModsHttpService.class).info("Shared mod listener ready on {}:{}: Market, Wardrobe, Season Pass and Journey", bind, port);
        } catch (Exception error) { server.stop(0); SeasonPassService.stop(); throw error; }
    }
    public static synchronized void stop() {
        if (listener != null) { listener.stop(1); listener = null; }
        PoetaJourneyHttpService.stop();
        SeasonPassHttpService.stop();
        CentralMarketHttpService.stop();
    }
}
