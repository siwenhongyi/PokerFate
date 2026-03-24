local P = class("HotSpringHallSkip", UiBase)

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    local Center = self:find("Center", AnimRoot)
    self.TextTitle = self:find("TextTitle", Center)
    self.TextContent = self:find("DecList/Viewport/Content/TextContent", Center)

    bee.addClick(self:find("hotspring_frame_bg/hotspring_btn_close", Center), function()
        self:hideUI()
    end)
    bee.addClick(self:find("btn_cancel", Center), function()
        self:hideUI()
    end)
    bee.addClick(self:find("btn_confirm", Center), function()
        self:hideUI()
        StoryModel:skipStory()
        Game:playSound("ui_button_confirm")
        bee.logEvent("onse-plot_skip_all", self._params.hotSpringdata.id, self._params.hotSpringdata.group, self._params.curData._index or 1)
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

