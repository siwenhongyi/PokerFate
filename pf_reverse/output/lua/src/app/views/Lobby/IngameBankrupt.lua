local P = class("IngameBankrupt", UiDialog)

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")

    self.TitleRoot = self:find("Protect/Title", self.Center)
    self.ClaimButton = self:find("Protect/ClaimButton", self.Center)
    self.TextChip = self:find("TextChip", self.Center)
    self.TextTip = self:find("Protect/Tips/TextTip", self.Center)

    local lan = LanguageManager:getLanguage()
    local count = self.TitleRoot.transform.childCount
    for i = 1, count do
        self.TitleRoot.transform:GetChild(i - 1).gameObject:SetActive(false)
    end
    self:find(string.format("Title_%s", lan), self.TitleRoot):SetActive(true)

    -- bee.addClick2(self:find("AnimRoot/Center/common_panel_mask_70"), function()
    --     self:hideUI()
    -- end)
    
    bee.addClick(self.ClaimButton, function()
        if bee.checkCd("BustProtectRewardREQ", 2) then
            Net:sendReq("pb.BustProtectRewardREQ", {})
        end
    end)
    bee.addClick(self:find("CloseButton", self.Center), function()
        self:hideUI()
    end)
end

function P:onShow()
    local msg = self._params and self._params.msg or {reward_chips = 1000, left_times = 3}
    bee.setText(self.TextChip, _N(msg.reward_chips))
    -- bee.setText(self.TextTip, _F("LAB_GAME_006", "<color=#F7FF2E>" .. msg.left_times .. "/" .. tpl_constdata.Bankruptcy_Protection_Times .. "</color>"))
    bee.setText(self.TextTip, _F("LAB_GAME_006", "" .. msg.left_times .. "/" .. tpl_constdata.Bankruptcy_Protection_Times .. ""))

    bee.logEvent("lobby-bankruptcy-protect")
end

function P:evt_BustProtectRewardRSP(msg)
    if msg.reward_chips and msg.reward_chips > 0 then
        bee.showUiTask("BackpackClaimResult", {items = {{item_id = GPropId.Gold, num = msg.reward_chips}}}, POP_TAG.Reward, LOBBY_POP_PRIORITY.Reward)
        bee.runTask(POP_TAG.Reward)
    end
    
    self:hideUI()
end

