-- Browser methods come from the client's bundled Widget.lua.
function PrivateCashShop_OnLoad()
    PrivateCashShopBrowser:CreateWebView();
    PrivateCashShop:Hide();
end

function PrivateCashShop_Open()
    PrivateCashShop:Show();
    PrivateCashShop:SetRect(0, 0, 1280, 960);
    PrivateCashShopBrowser:LoadUrlWithWebAuth(PRIVATE_CASH_SHOP_URL);
end

function PrivateWarehouse_OnLoad()
    PrivateWarehouseBrowser:CreateWebView();
    PrivateWarehouse:Hide();
end

function PrivateWarehouse_Open()
    PrivateWarehouse:Show();
    PrivateWarehouse:SetText("Central Market");
    -- Queue a native layout pass after Show. The market-specific resize hook
    -- replaces this XML seed with the current viewport and sizes its browser.
    PrivateWarehouse:SetRect(0, 0, 1280, 960);
    PrivateWarehouseBrowser:LoadUrlWithWebAuth(PRIVATE_CENTRAL_MARKET_URL);
end

function PrivateSeasonPass_Open()
    -- Reuse the already verified, viewport-sized native browser dialog.
    PrivateWarehouse:Show();
    PrivateWarehouse:SetText("Aetherfall Season Pass");
    PrivateWarehouse:SetRect(0, 0, 1280, 960);
    PrivateWarehouseBrowser:LoadUrlWithWebAuth(PRIVATE_SEASON_PASS_URL);
end

function PrivateCompanions_Open()
    PrivateWarehouse:Show();
    PrivateWarehouse:SetText("Player Companions");
    PrivateWarehouse:SetRect(0, 0, 1280, 960);
    PrivateWarehouseBrowser:LoadUrlWithWebAuth(PRIVATE_PLAYERBOTS_URL);
end

function PrivateWardrobe_OnLoad()
    WardrobeNative_OnLoad();
end

function PrivateWardrobe_Open()
    WardrobeNative_Open();
end

function PrivateJourney_OnLoad()
    PrivateJourneyBrowser:CreateWebView();
    PrivateJourney:Hide();
    this:RegisterEvent("PLAYER_ENTERING_WORLD");
end

function PrivateJourney_OnEvent(this, event, ...)
    if event == "PLAYER_ENTERING_WORLD" then
        PrivateJourney:Hide();
        -- A hidden, authenticated state request shows the choice only for an
        -- eligible character who has not already chosen to play Poeta.
        PrivateJourneyBrowser:LoadUrlWithWebAuth(PRIVATE_JOURNEY_URL);
    end
end

function PrivateJourney_Open()
    PrivateJourney:Show();
    PrivateJourney:SetRect(0, 0, 1280, 960);
    PrivateJourneyBrowser:LoadUrlWithWebAuth(PRIVATE_JOURNEY_URL);
end

function PrivateMenus_Register()
    SlashCmdList["PRIVATECOMPANIONS"] = PrivateCompanions_Open;
    SLASH_PRIVATECOMPANIONS1 = "/companions";
    RegisterMenu("Player Companions", SLASH_PRIVATECOMPANIONS1, "v5_start_menu_relic_up");
    SlashCmdList["PRIVATESEASONPASS"] = PrivateSeasonPass_Open;
    SLASH_PRIVATESEASONPASS1 = "/seasonpass";
    -- The incremental pass package supplies its own ticket skin/registration.
    -- The general menu builder can also target clients without that resource.
    RegisterMenu("Aetherfall Season Pass", SLASH_PRIVATESEASONPASS1, PRIVATE_SEASON_PASS_ICON or "v5_start_menu_relic_up");
    SlashCmdList["PRIVATEJOURNEY"] = PrivateJourney_Open;
    SLASH_PRIVATEJOURNEY1 = "/journey";
    RegisterMenu("Choose Your Journey", SLASH_PRIVATEJOURNEY1, "v5_start_menu_relic_up");
    SlashCmdList["PRIVATECASHSHOP"] = PrivateCashShop_Open;
    SLASH_PRIVATECASHSHOP1 = "/privatecashshop";
    SlashCmdList["PRIVATEWAREHOUSE"] = PrivateWarehouse_Open;
    SLASH_PRIVATEWAREHOUSE1 = "/privatewarehouse";
    SlashCmdList["PRIVATEWARDROBE"] = PrivateWardrobe_Open;
    SLASH_PRIVATEWARDROBE1 = "/wardrobe";
    for _, entry in ipairs(PRIVATE_SERVER_MENUS) do
        if entry.command == "transmog" then
            RegisterMenu(entry.label, SLASH_PRIVATEWARDROBE1, entry.icon);
        elseif entry.command == "warehouse" then
            RegisterMenu(entry.label, SLASH_PRIVATEWAREHOUSE1, entry.icon);
        else
            RegisterMenu(entry.label, "/say ." .. entry.command, entry.icon);
        end
    end
    -- The native HUD Shop shortcut opens PRIVATECASHSHOP directly.
end
