local P = class("GoldItem", Object)

function P:setItemId(id)
    bee.removeAllClick(self.node)
    bee.addClick(self.node, function()
        Game:playSound("ui_button_confirm")
        ItemModel:jumpViewByItemId(id)
        if self._cb then
            self._cb()
        end
    end, true)

    bee.removeAllClick(self:find("Icon"))
    bee.addClick(self:find("Icon"), function()
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(id, true), target = self:find("Icon")})
    end, true)

    local d = tpl_props[id]
    if d then
        bee.setIcon(self:find("Icon"), d.icon)
    end
end

function P:setCount(count)
    bee.setText(self:find("CountText"), count)
end

function P:setClickCallback(cb)
    self._cb = cb
end

