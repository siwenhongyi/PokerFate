local P = class("HotSpringRule", UiFullView)

function P:onAwake()
    self._isMute = true
    
    self.Center = self:find("AnimRoot/Center")
    self.RuleList = self:find("RuleList", self.Center)
    self.PageView = self.RuleList:GetComponent("PageView")
    self.ButtonLeft = self:find("ButtonLeft", self.Center)
    self.ButtonRight = self:find("ButtonRight", self.Center)

    self.Content = self:find("Viewport/Content", self.RuleList)

    bee.addClick(self:find("AnimRoot/RightTop/CloseButton"), function()
        Game:playSound("ui_button_confirm")
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
    self:refreshUI()
end

function P:refreshUI()
    self.ButtonLeft:SetActive(self.PageView:GetCurIndex() > 0)
    self.ButtonRight:SetActive(self.PageView:GetCurIndex() < self.PageView:GetPageCount() - 1)
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

