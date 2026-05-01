local P = class("VIPUpgrade", UiDialog)


function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Upgrade = self:find("Center/Upgrade", self.AnimRoot)
    
    self.ImageIcon = self:find("ImageIcon", self.Upgrade)
    self.TextLevel1 = self:find("shop_vipupgrade_bg_02/TextLevel1", self.Upgrade)
    self.TextLevel2 = self:find("shop_vipupgrade_bg_02/TextLevel2", self.Upgrade)

    self.AttrList = self:find("AttrList", self.Upgrade)
    self.Content = self:find("Viewport/Content", self.AttrList)
    
    self.Level01Attrs = {
        daily_gift_counts = self:find('shop_vipupgrade_bg_4/daily_gift_counts_01', self.Content),
        friend_limit = self:find('shop_vipupgrade_bg_8/friend_limit_01', self.Content),
        blacklist_limit = self:find('shop_vipupgrade_bg_9/blacklist_limit_01', self.Content),
        sheet_limit = self:find('shop_vipupgrade_bg_7/sheet_limit_01', self.Content),
        plan_limit = self:find('plan_limit_01', self.Content),
        exp_hands = self:find('shop_vipupgrade_bg_2/exp_hands_01', self.Content),
        friendship_hands = self:find('shop_vipupgrade_bg_3/friendship_hands_01', self.Content),
        vip_add = self:find('shop_vipupgrade_bg_1/vip_add_01', self.Content),
        exp_tournament = self:find('shop_vipupgrade_bg_5/exp_tournament_01', self.Content),
        friendship_tournament = self:find('shop_vipupgrade_bg_6/friendship_tournament_01', self.Content),
        recent_history_limit = self:find('shop_vipupgrade_bg_10/recent_history_limit_01', self.Content),
    }
    
    self.Level02Attrs = {
        daily_gift_counts = self:find('shop_vipupgrade_bg_4/daily_gift_counts_02', self.Content),
        friend_limit = self:find('shop_vipupgrade_bg_8/friend_limit_02', self.Content),
        blacklist_limit = self:find('shop_vipupgrade_bg_9/blacklist_limit_02', self.Content),
        sheet_limit = self:find('shop_vipupgrade_bg_7/sheet_limit_02', self.Content),
        plan_limit = self:find('plan_limit_02', self.Content),
        exp_hands = self:find('shop_vipupgrade_bg_2/exp_hands_02', self.Content),
        friendship_hands = self:find('shop_vipupgrade_bg_3/friendship_hands_02', self.Content),
        vip_add = self:find('shop_vipupgrade_bg_1/vip_add_02', self.Content),
        exp_tournament = self:find('shop_vipupgrade_bg_5/exp_tournament_02', self.Content),
        friendship_tournament = self:find('shop_vipupgrade_bg_6/friendship_tournament_02', self.Content),
        recent_history_limit = self:find('shop_vipupgrade_bg_10/recent_history_limit_02', self.Content),
    }

    bee.addClick(self.Upgrade, function()
        self:hideUI()
    end)

    Game:playSound("ui_vip_upgrade")
end

function P:onShow()
    local oldLevel = self._params and self._params.oldLevel or (VipModel:getVipLevel() - 1)
    self:refreshAttrs(oldLevel, self.Level01Attrs)
    self:refreshAttrs(VipModel:getVipLevel(), self.Level02Attrs)

    local d = tpl_vip_level[VipModel:getVipLevel()] or tpl_vip_level_list[#tpl_vip_level_list]

    bee.setIcon(self.ImageIcon, d.icon)
    bee.setText(self.TextLevel1, _F("LAB_VIP_TEXT_23", oldLevel))
    bee.setText(self.TextLevel2, _F("LAB_VIP_TEXT_23", VipModel:getVipLevel()))

    local scroll = self.AttrList:GetComponent("ScrollRect")
    scroll.enabled = false
    self:once(0.8, function()
        scroll.enabled = true
        bee.Tween.toFloat(1, 0, 0.5, function(v)
            scroll.verticalNormalizedPosition = v
        end)
    end)
end

function P:refreshAttrs(level, attrs)
    local d = tpl_vip_level[level] or tpl_vip_level_list[#tpl_vip_level_list]
    if d then
        for k, v in pairs(attrs) do
            if "vip_add" == k then
                bee.setText(v, tostring(d[k] / 10) .. "%")
            else
                bee.setText(v, tostring(d[k]))
            end
        end
    else
        for k, v in pairs(attrs) do
            bee.setText(v, "0")
        end
    end
end

return P