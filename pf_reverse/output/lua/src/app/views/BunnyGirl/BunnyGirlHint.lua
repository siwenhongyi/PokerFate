local P = class("BunnyGirlHint", UiBase)

function P:onAwake()
    self.Panel = self:find("AnimRoot/Center/Panel")

    self.TextTip = self:find("TextTip", self.Panel)

    bee.addClick(self:find("CancelButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConfirmButton", self.Panel), function()
        UiManager:showUI("BunnyGirlStory")
        self:hideUI()
    end)
    bee.addClick(self:find("bunnygirl_tc_btn_close", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end, true)
end

function P:onShow()
    if self._params and self._params.item and tpl_props[self._params.item.item_id] then
        local mapId = tpl_props[self._params.item.item_id].mapId
        local d = tpl_character[mapId]
        if d then
            bee.setText(self.TextTip, _F("LAB_THEME_ACTIVITY4_7", _T(d.name)))
        end
    end
end

return P