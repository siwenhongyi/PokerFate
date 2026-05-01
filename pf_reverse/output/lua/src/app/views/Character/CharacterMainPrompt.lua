local P = class("CharacterMainPrompt", UiBase)

function P:onAwake()
    local Center = self:find("AnimRoot/Center")
    local Panel = self:find("Panel", Center)
    self.Item = self:find("Item", Panel)

    bee.addClick(self:find("CloseButton", Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("CancelButton", Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConsumeButton", Panel), function()
        if self._params and self._params.onSure then
            self._params.onSure()
        end
        self:hideUI()
    end)
    
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end)
end

function P:onShow()
    self._data = self._params and self._params.data
    if self._data then
        local d = tpl_props[self._data.item_id]
        if d then
            bee.setIcon(self:find("icon", self.Item), d.icon)
            bee.setText(self:find("TextName", self.Item), _T(d.name))
        end
    end
end

return P