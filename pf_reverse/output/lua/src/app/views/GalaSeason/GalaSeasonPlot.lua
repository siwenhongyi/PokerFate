local P = class("GalaSeasonPlot", UiBase)

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    local Center = self:find("Center", AnimRoot)
    self.Panel = self:find("AnimRoot/Center/Panel")
    self.TextTitle = self:find("GalaSeason_bg_tc_db_02/TextTitle", self.Panel)
    self.TextContent = self:find("ContentList/Viewport/Content/TextContent", self.Panel)

    bee.addClick(self:find("Popup/GalaSeason_btn_tc_close", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("CancelButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConfirmButton", self.Panel), function()
        self:hideUI()
        StoryModel:skipStory()
        Game:playSound("ui_button_confirm")
        bee.logEvent("galaseason-plot_skip_all", StoryModel.storyData.id, StoryModel.storyData.group, self._params.curData._index or 1)
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end, true)
end

function P:onShow()
    local data = StoryModel:getStoryData()
    if data then
        bee.setText(self.TextTitle, _T(data.name))
        bee.setText(self.TextContent, _T(data.dec))
    end
end

