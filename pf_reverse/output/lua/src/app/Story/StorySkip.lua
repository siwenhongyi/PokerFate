local P = class("StorySkip", UiBase)

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    local Panel = self:find("Center/Panel", AnimRoot)
    self.TextTitle = self:find("TextTitle", Panel)
    self.TextContent = self:find("DecList/Viewport/Content/TextContent", Panel)

    bee.addClick(self:find("CloseButton", Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("CancelButton", Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConfirmButton", Panel), function()
        self:hideUI()
        StoryModel:skipStory()
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

return P