local P = class("ItemData")

function P:ctor(data)
    self:setData(data)
end

function P:setData(data)
    self.item_id = data.item_id
    self.item_uniq_id = data.item_uniq_id
    self.num = data.num
    self.deadline = data.deadline
    self.locked = data.locked

    local d = tpl_props[self.item_id]
    if d then
        for k, v in pairs(d) do
            self[k] = v
        end
        self._no_data = false
    else
        self._no_data = true
    end
end

function P:isLocked()
    return self.locked or self.num <= 0
end

function P:isDecorate()
    return self.type == GPropKind.CardBack or
        self.type == GPropKind.Table or
        self.type == GPropKind.MusicLobby or
        self.type == GPropKind.MusicTable or
        self.type == GPropKind.LobbyScene
end

function P:getDeadLeftTime()
    if self.deadline and self.deadline > 0 then
        local left = self.deadline - bee.getServerTime()
        return left > 0 and left or 0
    end
    return 0
end

