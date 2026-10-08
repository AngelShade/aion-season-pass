function PrivateWarehouse_OnLoad()
    PrivateWarehouseBrowser:CreateWebView();
    PrivateWarehouse:Hide();
end
function PrivateSeasonPass_Open()
    PrivateWarehouse:Show();
    PrivateWarehouse:SetText("Aetherfall Season Pass");
    PrivateWarehouse:SetRect(0,0,1280,960);
    PrivateWarehouseBrowser:LoadUrlWithWebAuth(PRIVATE_SEASON_PASS_URL);
end
function PrivateMenus_Register()
    SlashCmdList["PRIVATESEASONPASS"] = PrivateSeasonPass_Open;
    SLASH_PRIVATESEASONPASS1 = "/seasonpass";
    RegisterMenu("Aetherfall Season Pass", SLASH_PRIVATESEASONPASS1, "season_ticket_up");
end
