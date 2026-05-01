local P = class("CharacterGiftResult", UiBase)

function P:onAwake()
    local Center = self:find("AnimRoot/Center")
    local Panel = self:find("Panel", Center)
    self.icon_item_01 = self:find("icon_item_01", Panel)

    bee.addClick(self:find("CloseButton", Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ClaimButton", Panel), function()
		Game:playSound("ui_button_confirm")
        if ItemModel:getItemNumById(GPropId.RoleGiftBox) > 0 then
            UiManager:showUI("BackpackGift", {id = GPropId.RoleGiftBox})
        else
            ItemModel:jumpView(103002)
        end
        self:hideUI()
    end)
    
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end)
end

function P:onShow()
    self._data = self._params.data
    if self._data then
        local d = tpl_props[self._data.item_id]
        if d then
            -- bee.setIcon(self.icon_item_01, d.icon, true)
        end
    end
end

return P