local P = class("LevelUpgrade", UiDialog)

function P:onAwake()
    self.Upgrade = self:find("AnimRoot/Center/Upgrade")
    self.Share = self:find("AnimRoot/Center/Share")
    self.Share:SetActive(false)

    self.ImageIcon = self:find("ImageIcon", self.Upgrade)
    self.TextLevel = self:find("level_upgrade_text_bg/TextLevel", self.Upgrade)
    self.Reward = self:find("Reward", self.Upgrade)
    self.Item = self:find("Item", self.Reward)
    self.Item:SetActive(false)

    local RightCont = self:find("AnimRoot/RightBottom")
    self.ShareCont = self:find("ShareCont", RightCont)
    self.ShareButton = self:find("ShareButton", self.ShareCont)
    self.ShareReward = self:find("ShareReward", self.ShareCont)

    bee.addClick(self:find("CloseMask", self.Upgrade), function()
        self:hideUI(nil, true)
    end)
    bee.addClick(self.ShareButton, function()
        UiManager:showUI("ShareMain", {id = 4, tipsText = _F("LAB_SHARE_LEVEL_DEC_1", PlayerModel:getCurLevel())})
    end)

    Game:playSound("ui_level_upgrade_lobby")
end

function P:onShow()
    local levels = self._params and self._params.levels or {PlayerModel:getCurLevel()}
    local info = tpl_level[PlayerModel:getCurLevel()]
    if info then
        bee.setIcon(self.ImageIcon, info.icon)
        bee.setText(self.TextLevel, _T(info.name) .. " " .. _F("LAB_LEVEL_TEXT_5", PlayerModel:getCurLevel()))
    end
    local rewards = {}
    for _, v in ipairs(levels) do
        info = tpl_level[v]
        if info then
            for _, v in ipairs(rewards) do
                if v.item_id == info.rewards[1] then
                    v.num = v.num + info.rewards[2]
                    info = nil
                    break
                end
            end
            if info and info.rewards then
                table.insert(rewards, {item_id = info.rewards[1], num = info.rewards[2]})
            end
        end
    end
    for _, v in ipairs(rewards) do
        local item = CU.GameObject.Instantiate(self.Item, self.Reward.transform, false)
        item:SetActive(true)
        PropItem:bindItemNode(item, v)
        : bindTips()
    end
    self:setShareCont()
end

function P:evt_shareShot()
    self.Upgrade:SetActive(false)
    self.Share:SetActive(true)
    self.ShareButton:SetActive(false)
    self.ShareReward:SetActive(false)

    local info = tpl_level[PlayerModel:getCurLevel()]
    if info then
        bee.setIcon(self:find("ImageIcon", self.Share), info.icon)
        bee.setText(self:find("level_upgrade_text_bg/TextLevel", self.Share), _T(info.name) .. " " .. _F("LAB_LEVEL_TEXT_5", PlayerModel:getCurLevel()))
    end
end

function P:evt_endShareShot()
    self.Upgrade:SetActive(true)
    self.Share:SetActive(false)
    self.ShareButton:SetActive(true)
    self:setShareCont()
end

function P:evt_updateSharedPage()
    self:setShareCont()
end

function P:setShareCont()
    local Icon = self:find("Icon", self.ShareReward)
    local CountText = self:find("CountText", self.ShareReward)
    ShareModel:setShareCont(self.ShareReward, Icon, CountText, 4)
end

