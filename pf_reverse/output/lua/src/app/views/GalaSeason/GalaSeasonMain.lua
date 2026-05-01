local P = class("GalaSeasonMain", require("app.views.GalaSeason.GalaSeasonBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.TextTime = self:find("Title/Tips/TIPS", self.LeftTop)

    bee.addClick(self:find("StoryButton", self.LeftBottom), function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        UiManager:showUI("GalaSeasonInvitation")
        bee.logEvent("galaseason-plot")
    end)
    bee.addClick(self:find("TaskButton", self.LeftBottom), function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        UiManager:showUI("GalaSeasonActivity")
        bee.logEvent("galaseason-task")
    end)
    bee.addClick(self:find("GachaButton", self.RightBottom), function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        ItemModel:jumpView(2003)
        bee.logEvent("galaseason-pool")
    end)
    bee.addClick(self:find("ShopButton", self.RightBottom), function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        UiManager:showUI("GalaSeasonShop")
        bee.logEvent("galaseason-shop")
    end)
    bee.addClick(self:find("SngButton", self.RightBottom), function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        UiManager:showUI("TournamentLobby")
        bee.logEvent("galaseason-sng")
    end)
    
    RedManager:bind(self:find("TaskButton/Reddot", self.LeftBottom), RedTag.GalaSeasonTask)
    RedManager:bind(self:find("StoryButton/Reddot", self.LeftBottom), RedTag.GalaSeasonPlot)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[100905], false)

    -- bee.setText(self.TextTime, _F("LAB_THEME_ACTIVITY_TIME", TimeHelp:getDateTimeStrM(ThemeModel._end_time, "/")))
    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.GalaSeason)
    bee.logEvent("galaseason-main")
end


return P