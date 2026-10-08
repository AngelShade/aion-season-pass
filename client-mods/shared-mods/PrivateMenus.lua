PRIVATE_SEASON_PASS_URL = "@ORIGIN@/market/pass";
PRIVATE_CENTRAL_MARKET_URL = "@ORIGIN@/market";
PRIVATE_WARDROBE_URL = "@ORIGIN@/market/wardrobe";
PRIVATE_JOURNEY_URL = "@ORIGIN@/journey";
function PrivateWarehouse_OnLoad()
    PrivateWarehouseBrowser:CreateWebView();
    PrivateWarehouse:Hide();
end
function PrivateCentralMarket_Open()
    PrivateWarehouse:Show(); PrivateWarehouse:SetText("Central Market");
    PrivateWarehouse:SetRect(0,0,1280,960);
    PrivateWarehouseBrowser:LoadUrlWithWebAuth(PRIVATE_CENTRAL_MARKET_URL);
end
function PrivateSeasonPass_Open()
    PrivateWarehouse:Show(); PrivateWarehouse:SetText("Aetherfall Season Pass");
    PrivateWarehouse:SetRect(0,0,1280,960);
    PrivateWarehouseBrowser:LoadUrlWithWebAuth(PRIVATE_SEASON_PASS_URL);
end
function PrivateWardrobe_OnLoad()
    PrivateWardrobeBrowser:CreateWebView(); PrivateWardrobe:Hide();
end
function PrivateWardrobe_Open()
    PrivateWardrobe:Show(); PrivateWardrobe:SetRect(0,0,1280,960);
    PrivateWardrobeBrowser:LoadUrlWithWebAuth(PRIVATE_WARDROBE_URL);
end
function PrivateJourney_OnLoad()
    PrivateJourneyBrowser:CreateWebView(); PrivateJourney:Hide();
    this:RegisterEvent("PLAYER_ENTERING_WORLD");
end
function PrivateJourney_OnEvent(this,event,...)
    if event == "PLAYER_ENTERING_WORLD" then
        PrivateJourney:Hide(); PrivateJourneyBrowser:LoadUrlWithWebAuth(PRIVATE_JOURNEY_URL);
    end
end
function PrivateJourney_Open()
    PrivateJourney:Show(); PrivateJourney:SetRect(0,0,1280,960);
    PrivateJourneyBrowser:LoadUrlWithWebAuth(PRIVATE_JOURNEY_URL);
end
function PrivateMenus_Register()
    SlashCmdList["PRIVATESEASONPASS"]=PrivateSeasonPass_Open; SLASH_PRIVATESEASONPASS1="/seasonpass";
    SlashCmdList["PRIVATEMARKET"]=PrivateCentralMarket_Open; SLASH_PRIVATEMARKET1="/centralmarket";
    SlashCmdList["PRIVATEWARDROBE"]=PrivateWardrobe_Open; SLASH_PRIVATEWARDROBE1="/wardrobe";
    SlashCmdList["PRIVATEJOURNEY"]=PrivateJourney_Open; SLASH_PRIVATEJOURNEY1="/journey";
    RegisterMenu("Aetherfall Season Pass",SLASH_PRIVATESEASONPASS1,"season_ticket_up");
    RegisterMenu("Central Market",SLASH_PRIVATEMARKET1,"mkt_scales_up");
    RegisterMenu("Wardrobe",SLASH_PRIVATEWARDROBE1,"v5_npc_func_skinchange");
    RegisterMenu("Choose Your Journey",SLASH_PRIVATEJOURNEY1,"v5_start_menu_relic_up");
end
