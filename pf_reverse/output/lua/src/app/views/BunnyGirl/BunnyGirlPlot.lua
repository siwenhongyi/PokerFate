local P = class("BunnyGirlPlot", UiDialog)

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    local Center = self:find("Center", AnimRoot)
    self.TitleFrame = self:find("Stitle/bunnygirl_tc_bg_stitle", Center)
    self.TextTitle = self:find("Stitle/TextTitle",Center)
    self.TextContent = self:find("ContentList/Viewport/Content/TextContent", Center)

    bee.addClick(self:find("bunnygirl_tc_btn_close", Center), function()
        self:hideUI()
    end)
    bee.addClick(self:find("CancelButton", Center), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConfirmButton", Center), function()
        self:hideUI()
        StoryModel:skipStory()
        Game:playSound("ui_button_confirm")
        -- bee.logEvent("galaseason-plot_skip_all", StoryModel.storyData.id, StoryModel.storyData.group, self._params.curData._index or 1)
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
        local titleText = self.TextTitle:GetComponent("Text")
        local width = titleText.preferredWidth + 100
        local rect = self.TitleFrame:GetComponent("RectTransform")
        rect.sizeDelta = bee.v2(width, rect.sizeDelta.y)
    end
end

return P