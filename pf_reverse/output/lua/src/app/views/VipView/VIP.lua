local P = class("VIP", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)
    self.RightTop = self:find("RightTop", self.AnimRoot)
    
    self.Gold = self:find("Gold", self.RightTop)
    self.Ticket1 = self:find("Ticket1", self.RightTop)
    self.Ticket2 = self:find("Ticket2", self.RightTop)

    self.TextRewardTitle = self:find("TextRewardTitle", self.Panel)
    self.LeftButton = self:find("LeftButton", self.Panel)
    self.RightButton = self:find("RightButton", self.Panel)

    local shop_vip_bg_02 = self:find("shop_vip_bg_02", self.Panel)
    self.ImageIcon = self:find("ImageIcon", shop_vip_bg_02)
    self.TextFullLevel = self:find("TextFullLevel", shop_vip_bg_02)
    self.UpgradeButton = self:find("UpgradeButton", shop_vip_bg_02)
    self.ClaimButton = self:find("ClaimButton", self.Panel)
    self.ClaimedButton = self:find("ClaimedButton", self.Panel)
    self.ReceivedButton = self:find("ReceivedButton", self.Panel)

    self.LevelSlider = self:find("LevelSlider", shop_vip_bg_02)
    self.TextExp = self:find("TextExp", self.LevelSlider)
    self.TextTip = self:find("TextTip", self.LevelSlider)
    self.shop_vip_bg_level_02 = self:find("shop_vip_bg_level_02", shop_vip_bg_02)

    local Title = self:find("shop_vip_bg_right/Title", self.Panel)
    self.ImageTitle = self:find("ImageTitle", Title)
    self.TextNoTitle = self:find("TextNoTitle", Title)
    self.TitleMask = self:find("TitleMask", Title)

    self.IconList = self:find("shop_vip_bg_right/IconList", self.Panel)
    self.Content = self:find("Viewport/Content", self.IconList)
    self.Item01 = self:find("Item01", self.IconList)
    self.Item01:SetActive(false)

    bee.addClick(self:find("BackButton", self.LeftTop), function()
        self:hideUI()
    end)
    bee.addClick(self:find("InfoButton", self.TextRewardTitle), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("VIPDetail")
        bee.logEvent("vip-rules")
    end)
    bee.addClick(self.UpgradeButton, function()
        if VipModel:getVipLevel() >= VipModel:getMaxLevel() then
            UiManager:showToast(_T("LAB_VIP_TEXT_6"))
            return
        end
        Game:playSound("ui_button_confirm")
        self:hideUI()
        ItemModel:jumpView(105001)
        bee.logEvent("vip-level-up")
    end)
    bee.addClick(self:find("AssistantButton", shop_vip_bg_02), function()
        bee.logEvent("vip-assistant")
        Game:playSound("ui_button_confirm")
    end)
    bee.addClick(self.ClaimButton, function()
        Game:playSound("ui_button_confirm")
        local level = self._curLevel
        VipModel:reqVipReward(level, function()
            if tpl_vip_level[level + 1] then
                self._curLevel = level + 1
            end
            for i = level + 1, VipModel:getVipLevel() do
                if not VipModel:isClaimedLevel(i) then
                    self._curLevel = i
                    break
                end
            end
            self:refreshUI()
            
            local d = tpl_vip_level[level]
            local items = {}
            if d.title then
                table.insert(items, {id = d.title, num = 1})
            end
            for i = 1, #d.rewards - 1, 2 do
                table.insert(items, {id = d.rewards[i], num = d.rewards[i + 1]})
            end
            UiManager:showUI("BackpackClaimResult", {
                items = items
            })
        end)
    end)
    bee.addClick(self.ClaimedButton, function()
        UiManager:showToast(_T("LAB_VIP_TEXT_18"))
    end)
    bee.addClick(self.ReceivedButton, function()
        UiManager:showToast(_T("LAB_VIP_TEXT_17"))
    end)
    bee.addClick(self.LeftButton, function()
        Game:playSound("ui_button_confirm")
        if not bee.checkCd("vip-left-right-button", 0.2) then
            return
        end
        self._curLevel = self._curLevel - 1
        self:refreshUI()
    end)
    bee.addClick(self.RightButton, function()
        Game:playSound("ui_button_confirm")
        if not bee.checkCd("vip-left-right-button", 0.2) then
            return
        end
        self._curLevel = self._curLevel + 1
        self:refreshUI()
    end)
    bee.addClick(self.ImageTitle, function()
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(tpl_vip_level[self._curLevel].title, true), target = self.ImageTitle})
    end)

    self.ShopVipList = self:find("ShopVipList/Viewport/Content", self.Panel)
    self.LevelAttrs = {
        daily_gift_counts = self:find('shop_vip_img_biao4/daily_gift_counts', self.ShopVipList),
        friend_limit = self:find('shop_vip_img_biao8/friend_limit', self.ShopVipList),
        blacklist_limit = self:find('shop_vip_img_biao9/blacklist_limit', self.ShopVipList),
        sheet_limit = self:find('shop_vip_img_biao7/sheet_limit', self.ShopVipList),
        plan_limit = self:find('plan_limit', self.ShopVipList),
        exp_hands = self:find('shop_vip_img_biao2/exp_hands', self.ShopVipList),
        friendship_hands = self:find('shop_vip_img_biao3/friendship_hands', self.ShopVipList),
        vip_add = self:find('shop_vip_img_biao1/vip_add', self.ShopVipList),
        exp_tournament = self:find('shop_vip_img_biao5/exp_tournament', self.ShopVipList),
        friendship_tournament = self:find('shop_vip_img_biao6/friendship_tournament', self.ShopVipList),
        recent_history_limit = self:find('shop_vip_img_biao10/recent_history_limit', self.ShopVipList),
    }

    if bee.isInTest then
    end
    self:find("AssistantButton", shop_vip_bg_02):SetActive(false)
end

function P:onShow()
    bee.invoke(self.Gold, "setItemId", GPropId.Gold)
    bee.invoke(self.Ticket1, "setItemId", GPropId.TicketDraw)
    bee.invoke(self.Ticket2, "setItemId", GPropId.TicketDress)
    self:evt_refreshTopInfo()

    if VipModel:getVipLevel() >= VipModel:getMaxLevel() then
        self.TextFullLevel:SetActive(true)
        self.UpgradeButton:SetActive(false)
    else
        self.TextFullLevel:SetActive(false)
        self.UpgradeButton:SetActive(true)
    end
    self._curLevel = VipModel:getVipLevel() + 1
    for i = 0, VipModel:getVipLevel() do
        if not VipModel:isClaimedLevel(i) then
            self._curLevel = i
            break
        end
    end
    if self._curLevel > VipModel:getMaxLevel() then
        self._curLevel = VipModel:getMaxLevel()
    end

    self:refreshUI()

    VipModel:reqVipData(function()
        if not bee.isNull(self.node) then
            self:refreshUI()
        end
    end)
    
    bee.logEvent("vip-view")
end

function P:refreshUI()
    self.shop_vip_bg_level_02:SetActive(self._curLevel == VipModel:getVipLevel())
    self.LeftButton:SetActive(self._curLevel > 0)
    self.RightButton:SetActive(self._curLevel < VipModel:getMaxLevel())

    local flag = VipModel:isClaimedLevel(self._curLevel)
    self.ClaimButton:SetActive(self._curLevel <= VipModel:getVipLevel() and not flag)
    self.ClaimedButton:SetActive(self._curLevel <= VipModel:getVipLevel() and flag)
    self.ReceivedButton:SetActive(self._curLevel > VipModel:getVipLevel())

    self:refreshAttrs()
end

function P:refreshAttrs()
    bee.setText(self.TextRewardTitle, _F("LAB_VIP_TEXT_8", self._curLevel))
    local d = tpl_vip_level[self._curLevel]
    bee.setIcon(self.ImageIcon, d.icon)
    if self._curLevel <= VipModel:getVipLevel() then
        bee.setText(self.TextTip, _T("LAB_VIP_TEXT_3"))
        bee.setText(self.TextExp, "")
        bee.setSliderValue(self.LevelSlider, 1)
    else
        local exp = tpl_vip_level[self._curLevel] and tpl_vip_level[self._curLevel].upgrade_exp or 0
        bee.setText(self.TextTip, _F("LAB_VIP_TEXT_4", "<color=#CE1C84>" .. (exp - VipModel:getVipExp()) .. "</color>", self._curLevel))
        bee.setText(self.TextExp, string.format("%d/%d", VipModel:getVipExp(), exp))
        bee.setSliderValue(self.LevelSlider, VipModel:getVipExp() / exp)
    end

    for k, v in pairs(self.LevelAttrs) do
        if "vip_add" == k then
            bee.setText(v, tostring(d[k] / 10) .. "%")
        else
            bee.setText(v, tostring(d[k]))
        end
    end

    local flag = VipModel:isClaimedLevel(self._curLevel)
    if not d.title then
        self.ImageTitle:SetActive(false)
        self.TextNoTitle:SetActive(true)
        self.TitleMask:SetActive(false)
    else
        self.ImageTitle:SetActive(true)
        self.TextNoTitle:SetActive(false)
        self.TitleMask:SetActive(flag)
        GF.setTitleImage(self.ImageTitle, d.title)
    end
    self:removeAllChildren(self.Content)
    self.Items = {}
    for i = 1, #d.rewards - 1, 2 do
        local item = CU.GameObject.Instantiate(self.Item01, self.Content.transform, false)
        item:SetActive(true)
        PropItem:bindItemNode(item, {id = d.rewards[i], num = d.rewards[i + 1]}): bindTips()
        self:find("Mask", item):SetActive(flag)
        table.insert(self.Items, item)
    end
end

function P:evt_refreshTopInfo()
    bee.invoke(self.Gold, "setCount", _N(PlayerModel:getGold()))
    bee.invoke(self.Ticket1, "setCount", _N(ItemModel:getItemNumById(GPropId.TicketDraw)))
    bee.invoke(self.Ticket2, "setCount", _N(ItemModel:getItemNumById(GPropId.TicketDress)))
end

function P:evt_vipLevelUp()
    self:refreshUI()
end

