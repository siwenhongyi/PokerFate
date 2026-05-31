local P = class("TournamentIngamePopup", UiBase)

function P:onAwake()
    self.Bottom = self:find("AnimRoot/Bottom")
    self.LeftBottom = self:find("AnimRoot/LeftBottom")
    self.Rest = self:find("Rest", self.Bottom)
    self.Notice = self:find("Notice", self.Bottom)

    self.RestTip = self:find("Rest", self.LeftBottom)
    self.NoticeTip = self:find("Notice", self.LeftBottom)
    self.SuccessTip = self:find("Success", self.LeftBottom)
end

function P:onShow()
    local data = GameModel.data
    if self._params then
        if self._params.is_rest then    -- 休息时间提示
            self.Bottom:SetActive(true)
            self.LeftBottom:SetActive(false)
            self.Notice:SetActive(false)
            self.Rest:SetActive(true)

            local dt = (data.room_info.break_left_time or 0) - (os.time() - (data.break_left_time_st or 0))
            bee.setText(self:find("TextTime", self.Rest), _F("LAB_TOURNAMENT_MTT_INFO18", TimeHelp:getTimeStrHMS(dt)))

            self:schedule(1, function()
                dt = (data.room_info.break_left_time or 0) - (os.time() - (data.break_left_time_st or 0))
                if dt <= 0 then
                    dt = 0
                    self:hideUI()
                end
                bee.setText(self:find("TextTime", self.Rest), _F("LAB_TOURNAMENT_MTT_INFO18", TimeHelp:getTimeStrHMS(dt)))
            end)
        elseif self._params.is_notice then   -- 同步发牌提示
            self.Bottom:SetActive(true)
            self.LeftBottom:SetActive(false)
            self.Notice:SetActive(true)
            self.Rest:SetActive(false)

            if 1 == data.table_status.wait_sync then
                bee.setText(self:find("TextTitle", self.Notice), _F("LAB_TOURNAMENT_MTT_INFO23"))
                bee.setText(self:find("TextTip", self.Notice), _F("LAB_TOURNAMENT_MTT_INFO24"))
            elseif 2 == data.table_status.wait_sync then
                bee.setText(self:find("TextTitle", self.Notice), _F("LAB_TOURNAMENT_MTT_INFO54"))
                bee.setText(self:find("TextTip", self.Notice), _F("LAB_TOURNAMENT_MTT_INFO55"))
            end
        elseif self._params.is_rest_tip then   -- 休息时间即将开始提示
            self.Bottom:SetActive(false)
            self.LeftBottom:SetActive(true)
            self.RestTip:SetActive(true)
            self.NoticeTip:SetActive(false)
            self.SuccessTip:SetActive(false)

            bee.setText(self:find("TextTip", self.RestTip), _F("LAB_TOURNAMENT_MTT_INFO17", TimeHelp:getTimeLeftStr(data.room_info.break_duration or 0)))
            
            self:once(2, function()
                self:hideUI()
            end)
        elseif self._params.is_bubble_tip then   -- 泡沫提示
            self.Bottom:SetActive(false)
            self.LeftBottom:SetActive(true)
            self.RestTip:SetActive(false)
            self.NoticeTip:SetActive(true)
            self.SuccessTip:SetActive(false)

            bee.setText(self:find("TextTip", self.NoticeTip), _F("LAB_TOURNAMENT_MTT_INFO22", self._params.data.reward_num + 1, self._params.data.reward_num))

            self:once(2, function()
                self:hideUI()
            end)
        elseif self._params.is_success_tip then   -- 成功入圈提示
            self.Bottom:SetActive(false)
            self.LeftBottom:SetActive(true)
            self.RestTip:SetActive(false)
            self.NoticeTip:SetActive(false)
            self.SuccessTip:SetActive(true)

            bee.setText(self:find("TextTip", self.SuccessTip), _F("LAB_TOURNAMENT_MTT_INFO26", self._params.data.my_rank, self._params.data.reward_num))
            
            self:once(2, function()
                self:hideUI()
            end)
        end
    end
end

return P