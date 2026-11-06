-- 派遣规则说明弹窗
-- 显示协会经营的玩法说明
local P = class("DispatchRules", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("AnimRoot/Center")
    self.RuleList = self:find("RuleList", self.Center)

    self.PageView = self.RuleList:GetComponent("PageView")
    self.ButtonLeft = self:find("ButtonLeft", self.Center)
    self.ButtonRight = self:find("ButtonRight", self.Center)

    -- 关闭按钮
    bee.addClick(self:find("RightTop/CloseButton", self.AnimRoot), function()
        self:hideUI()
    end)

    bee.addClick(self.ButtonLeft, function()
        Game:playSound("ui_button_confirm")
        if self.PageView:GetCurIndex() > 0 then
            self.PageView:PageTo(self.PageView:GetCurIndex() - 1);
            self:refreshUI()
        end
    end)
    bee.addClick(self.ButtonRight, function()
        Game:playSound("ui_button_confirm")
        if self.PageView:GetCurIndex() < self.PageView:GetPageCount() - 1 then
            self.PageView:PageTo(self.PageView:GetCurIndex() + 1);
            self:refreshUI()
        end
    end)
    self.PageView:OnPageChange(function()
        self:refreshUI()
    end)
end

function P:onShow()
    local params = self._params or {}

    -- 内容容器
    local Rules = self:find("Viewport/Content/Rules", self.RuleList)
    local Content = self:find("ScrollView/Viewport/Content", Rules)

    local isUseEn = LAN:getLanguage() == "en"
    for i = 1, 3 do
        local TextList = self:find("TextList" .. i, Content)
        if TextList then
            for j = 1, 4 do
                local TIPS = self:find("TIPS" .. j, TextList)
                if TIPS then
                    local ingame_rules_title_star = self:find("ingame_rules_title_star", TIPS)
                    if ingame_rules_title_star then
                        ingame_rules_title_star:SetActive(isUseEn)
                        self:find("ingame_rules_title_star2", TIPS):SetActive(not isUseEn)
                    end
                end
            end
        end
    end

    bee.setText(self:find("TextList1/TIPS4", Content), _F("LAB_DISPATCH_67", _T(tpl_props[GPropId.RefreshDispatch].name)))
    bee.setText(self:find("TextList1/TIPS6", Content), _F("LAB_DISPATCH_131", tpl_constdata.Dispatch_Advanced_Num))

    local Type = self:find("Viewport/Content/Type/ScrollView/Viewport/Content/Table", self.RuleList)
    local Types = {
        self:find("type1", Type),
        self:find("type2", Type),
        self:find("type3", Type),
        self:find("type4", Type)
    }
    for k, v in ipairs(tpl_camp_info_list) do
        bee.setText(self:find("Text" .. k, Types[2]), v.members_limit)
        if 0 == v.time_reduce then
            bee.setText(self:find("Text" .. k, Types[3]), _T("LAB_TOURNAMENT_MTT_INFO129"))
        else
            bee.setText(self:find("Text" .. k, Types[3]), "" .. v.time_reduce / 100 .. "%")
        end
        if 0 == v.base_reward_up then
            bee.setText(self:find("Text" .. k, Types[4]), _T("LAB_TOURNAMENT_MTT_INFO129"))
        else
            bee.setText(self:find("Text" .. k, Types[4]), "" .. v.base_reward_up / 100 .. "%")
        end
    end

    self:refreshUI()
end

function P:refreshUI()
    self.ButtonLeft:SetActive(self.PageView:GetCurIndex() > 0)
    self.ButtonRight:SetActive(self.PageView:GetCurIndex() < self.PageView:GetPageCount() - 1)
end

return P