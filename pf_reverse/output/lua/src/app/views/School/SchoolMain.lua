local P = class("SchoolMain", require("app.views.School.SchoolBase"))

function P:onAwake()
    P.super.onAwake(self)

    self.LeftBottom = self:find("LeftBottom", self.AnimRoot)
    self.TaskButton = self:find("TaskButton", self.LeftBottom)
    self.ShopButton = self:find("ShopButton", self.LeftBottom)
    self.RightBottom = self:find("RightBottom", self.AnimRoot)
    self.StoryButton = self:find("StoryButton", self.RightBottom)
    self.GachaButton = self:find("GachaButton", self.RightBottom)

    bee.addClick(self.TaskButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SchoolTask")
    end)

    bee.addClick(self.ShopButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SchoolShop")
    end)

    bee.addClick(self.StoryButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SchoolStory")
    end)

    bee.addClick(self.GachaButton, function()
        Game:playSound("ui_button_confirm")
        
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self:hideUI()
            return
        end
        ItemModel:jumpView(2004)
        -- bee.logEvent("galaseason-pool")
    end)

    RedManager:bind(self:find("TaskButton/School_main_title_task_zh/Reddot", self.LeftBottom), RedTag.SchoolTask)
    RedManager:bind(self:find("StoryButton/School_main_title_story_zh/Reddot", self.RightBottom), RedTag.SchoolPlot)

    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.School)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[101305], false)

    -- bee.logEvent("galaseason-main")
end


return P