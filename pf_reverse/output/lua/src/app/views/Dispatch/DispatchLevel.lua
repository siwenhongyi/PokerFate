-- 事务所品质提升弹窗
-- 显示事务所等级提升后的奖励变化
local P = class("DispatchLevel", UiDialog)

function P:onAwake()
    local Center = self:find("AnimRoot/Center")

    self.CampBg = self:find("Camp/CampBg", Center)
    self.CampIcon = self:find("Camp/CampIcon", Center)
    self.CampNameText = self:find("CampNameText", Center)

    self.Levels = {
        self:find("Level1", Center),
        self:find("Level2", Center),
        self:find("Level3", Center),
        self:find("Level4", Center),
        self:find("Level5", Center),
    }

    self.Efts = {
        false,
        self:find("Eff_poker_Ui_DispatchLevel01", Center),
        self:find("Eff_poker_Ui_DispatchLevel02", Center),
        self:find("Eff_poker_Ui_DispatchLevel03", Center),
        self:find("Eff_poker_Ui_DispatchLevel04", Center),
    }

    -- 奖励列表
    local Item = self:find("Item", Center)
    self.Items = {
        self:find("Item1", Item),
        self:find("Item2", Item),
        self:find("Item3", Item),
        self:find("Item4", Item),
    }

    -- 关闭按钮事件
    bee.addClick2(self:find("bg_dispatch_level_01", Center), function()
        self:hideUI()
    end)

    Game:playSound("ui_vip_upgrade")
end


function P:onShow()
    local params = self._params or {}

    local camp = params.camp_id or 0
    local curLevel = DispatchModel:getCampLevel(camp)
    local preLevel = curLevel - 1
    if preLevel <= 0 then
        preLevel = 1
        curLevel = 2
    end

    for k, v in ipairs(self.Levels) do
        v:SetActive(k == curLevel)
    end
    for k, v in ipairs(self.Efts) do
        if v then
            v:SetActive(k == curLevel)
        end
    end

    bee.setIcon(self.CampBg, "dispatch_level_tap_camp_bg_" .. curLevel, "Dispatch")
    bee.setIcon(self.CampIcon, tpl_camp_detail[camp].camp_icon)
    bee.setText(self.CampNameText, _F("LAB_DISPATCH_02", _T(tpl_camp_detail[camp].camp_name)))

    local d1, d2 = tpl_camp_info[curLevel], tpl_camp_info[preLevel]

    self:find("Ani_root/TextBaseLevel" .. preLevel, self.Items[1]):SetActive(true)
    self:find("Ani_root/TextLevel" .. curLevel, self.Items[1]):SetActive(true)

    bee.setText(self:find("Ani_root/TextBase", self.Items[2]), d2.members_limit)
    bee.setText(self:find("Ani_root/TextUp", self.Items[2]), d1.members_limit)
    self.Items[2]:SetActive(d1.members_limit ~= d2.members_limit)

    bee.setText(self:find("Ani_root/TextBase", self.Items[3]), "" .. d2.time_reduce / 100 .. "%")
    bee.setText(self:find("Ani_root/TextUp", self.Items[3]), "" .. d1.time_reduce / 100 .. "%")

    bee.setText(self:find("Ani_root/TextBase", self.Items[4]), "" .. d2.base_reward_up / 100 .. "%")
    bee.setText(self:find("Ani_root/TextUp", self.Items[4]), "" .. d1.base_reward_up / 100 .. "%")

    local index = 1
    for k, v in ipairs(self.Items) do
        if v.activeSelf then
            v:SetActive(false)
            self:once(0.8 + (index - 1) * 0.2, function()
                v:SetActive(true)
                self:playAnimator("UI_1_DispatchStar_item", self:find("Ani_root", v))
            end)
            index = index + 1
        end
    end
end

return P