local P = class("IngameNoticeSave", UiBase)

function P:onAwake()
    self.Panel = self:find("AnimRoot/RightBottom/Notice")
    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConfirmButton", self.Panel), function()
		RecordDataModel:addCollect(self._params.gameid, function(ok)
			if ok then
				RecordDataModel:markCollectDirty()
			end
		end, tostring(self._params.roomid), tostring(self._params.tid))
        self:hideUI()
    end)
    bee.addClick(self:find("CancelButton", self.Panel), function()
        self:hideUI()
    end)

    bee.setText(self:find("TextCap", self.Panel), "<color=#000000>" .. _F("LAB_SAVE_LIMIT", "</color>" .. PlayerModel:getCurRecord() .. " / " .. PlayerModel:getRecordNum()))
end

return P