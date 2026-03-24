local P = class("HotSpringHall", require("app.views.Hotspring.HotSpringBase"))

function P:onAwake()
    P.super.onAwake(self)
    -- self._tips = {"LAB_STORY_DIALOGUE_S1_1008_01", "LAB_STORY_DIALOGUE_S1_1008_02", "LAB_STORY_DIALOGUE_S1_1008_03"}
    self._tips = nil

    self.TextTime = self:find("title_activity/TextTime", self.LeftBottom)
    self.TextCount = self:find("Ticket2/TextCount", self.RightTop)

    bee.addClick(self:find("hotspring_btn_tips", self.LeftTop), function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        UiManager:showUI("HotSpringHallRule")
        self:find("hotspring_btn_tips/Eff_poker_Ui_hotspring_wh_loop", self.LeftTop):SetActive(false)
    end)
    bee.addClick(self:find("btn_entrance_task", self.RightBottom), function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        UiManager:showUI("HotSpringTask")
        bee.logEvent("onsen-task")
    end)
    bee.addClick(self:find("btn_entrance_shop", self.RightBottom), function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        UiManager:showUI("HotSpringShop")
        bee.logEvent("onsen-shop")
    end)
    bee.addClick(self:find("btn_entrance_extraction", self.RightBottom), function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        ItemModel:jumpView(2002)
        bee.logEvent("onsen-pool")
    end)
    bee.addClick(self:find("btn_plot", self.RightBottom), function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        UiManager:showUI("HotSpringPlot")
        bee.logEvent("onsen-plot")
    end)
    bee.addClick(self:find("btn_aLLin", self.RightBottom), function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        UiManager:showUI("HotSpringHallBlind")
        bee.logEvent("onsen-all_in")
    end)

    RedManager:bind(self:find("btn_entrance_task/Reddot", self.RightBottom), RedTag.HotSpringTask)
end

function P:onShow()
    P.super.onShow(self)
    bee.logEvent("onsen-main")

    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[100301], true)

    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.HotSpring)
    bee.setText(self.TextTime, TimeHelp:getDateStr(ThemeModel._start_time, ".") .. " ~ " .. TimeHelp:getDateStr(ThemeModel._end_time, "."))

    self:find("hotspring_btn_tips/Eff_poker_Ui_hotspring_wh_loop", self.LeftTop):SetActive(LocalStore:isTagValid("Eff_poker_Ui_hotspring_wh_loop"))
end

