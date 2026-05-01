local P = class("IngameRules", UiDialog)

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")
    self.RuleList = self:find("RuleList", self.Center)
    self.PageView = self.RuleList:GetComponent("PageView")
    self.ButtonLeft = self:find("ButtonLeft", self.Center)
    self.ButtonRight = self:find("ButtonRight", self.Center)

    self.Content = self:find("Viewport/Content", self.RuleList)
    self.RulesOmaha = self:find("RulesOmaha", self.Center)
    self.RulesPoker = self:find("Rules", self.Content)

    bee.addClick(self:find("AnimRoot/RightTop/CloseButton"), function()
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

    -- 任务-查看角色界面
    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.HandExplanation)
end

function P:onShow()
    local isOmaha = GameModel.data and GameModel.data:isOmaha()
    if self._params and self._params.gameType then
        isOmaha = GF.isOmahaGame(self._params.gameType)
    end
    self.RulesOmaha:SetActive(isOmaha)
    if isOmaha then
        self.RulesPoker:SetActive(false)
        self.RulesPoker.transform:SetParent(self.Center.transform, false)
        self.RulesOmaha.transform:SetParent(self.Content.transform, false)
        self.RulesOmaha.transform:SetAsFirstSibling()
    elseif (GameModel.data and GameModel.data:isAllinOrFold()) or (self._params and self._params.gameType == GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN) then
        local rule = bee.createObj("views/Allin/AllinRules")
        rule.transform:SetParent(self.Content.transform, false)
        rule.transform:SetAsFirstSibling()
    end
    self:refreshUI()

    if not isOmaha then
        if LanguageManager:getLanguage() == "en" then
            self:find("Rules/TextList/TIPS1/ingame_rules_title_star", self.Content):SetActive(true)
            self:find("Rules/TextList/TIPS1/ingame_rules_title_star2", self.Content):SetActive(false)
            self:find("Rules/TextList/TIPS2/ingame_rules_title_star", self.Content):SetActive(true)
            self:find("Rules/TextList/TIPS2/ingame_rules_title_star2", self.Content):SetActive(false)
        else
            self:find("Rules/TextList/TIPS1/ingame_rules_title_star", self.Content):SetActive(false)
            self:find("Rules/TextList/TIPS1/ingame_rules_title_star2", self.Content):SetActive(true)
            self:find("Rules/TextList/TIPS2/ingame_rules_title_star", self.Content):SetActive(false)
            self:find("Rules/TextList/TIPS2/ingame_rules_title_star2", self.Content):SetActive(true)
        end
    end
end

function P:refreshUI()
    self.ButtonLeft:SetActive(self.PageView:GetCurIndex() > 0)
    self.ButtonRight:SetActive(self.PageView:GetCurIndex() < self.PageView:GetPageCount() - 1)
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

return P