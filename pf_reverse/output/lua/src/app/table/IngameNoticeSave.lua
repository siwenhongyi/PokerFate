local P = class("IngameNoticeSave", UiBase)

function P:onAwake()
    self.Panel = self:find("AnimRoot/RightBottom/Notice")
    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConfirmButton", self.Panel), function()
        Net:post("/collCard/update", {
            add_id = self._params.gameid,
            roomid = tostring(self._params.roomid),
            tid = tostring(self._params.tid),
        }, function(d)
            if 0 == d.code then
                PlayerModel:setCurRecord(#d.gameids)
            end
        end)
        self:hideUI()
    end)
    bee.addClick(self:find("CancelButton", self.Panel), function()
        self:hideUI()
    end)

    bee.setText(self:find("TextCap", self.Panel), "<color=#000000>" .. _F("LAB_SAVE_LIMIT", "</color>" .. PlayerModel:getCurRecord() .. " / " .. PlayerModel:getRecordNum()))
end

return P