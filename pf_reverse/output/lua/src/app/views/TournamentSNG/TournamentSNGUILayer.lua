local P = class("TournamentSNGUILayer", require("app.table.PK.PKUILayer"))

function P:onAwake()
    P.super.onAwake(self)

    self.BlindsInfo2 = self:find("BlindsInfo2", self.LeftTop)
    self.BlindsInfo3 = self:find("BlindsInfo3", self.LeftTop)
    self.PrizePool = self:find("PrizePool", self.RightTop)

    self.TextTime = self:find("TextTime", self.BlindsInfo2)
    self.TextBlind = self:find("TextBlind", self.BlindsInfo3)
    self.TextTitle = self:find("TextTitle", self.BlindsInfo3)
    self.TextBlindNext = self:find("TextBlindNext", self.BlindsInfo2)
    
    self.TextRank = self:find("TextRank", self.PrizePool)
    self.TextPrizePool = self:find("TextPrizePool", self.PrizePool)

    bee.addClick(self:find("StatsButton", self.RightTop), function()
        UiManager:showUI("TournamentSNGingame")
        Game:playSound("ui_button_confirm")
    end)
end

function P:onShow()
    P.super.onShow(self)

    self:evt_refreshPrizePool()
    self:evt_TourRoomRankRefreshBRC()

    bee.setText(self.TextTitle, GameModel.data:getGameName())
end

function P:getBlindText(sb, bb, ante)
    if ante and ante > 0 then
        return _F("<color=#FFBE18>{p1}({p2})</color>", _N(sb) .. "/" .. _N(bb), _N(ante))
    else
        return _F("<color=#FFBE18>{p1}</color>", _N(sb) .. "/" .. _N(bb))
    end
end

function P:evt_refreshPrizePool(force)
    if GameModel.data:isSngStart() or force then
        if 0 == GameModel.data.room_info.total_reward then
            local s = "-"
            if GameModel.data.rank_list and #GameModel.data.rank_list > 0 then
                for k, v in ipairs(GameModel.data.rank_list[1].reward_item_list) do
                    if v.item_id == GPropId.Gold then
                        s = _N(v.item_num)
                    end
                    break
                end
            end
            bee.setText(self.TextPrizePool, s)
        else
            bee.setText(self.TextPrizePool, _N(GameModel.data.room_info.total_reward))
        end
    else
        bee.setText(self.TextPrizePool, "-")
        -- bee.setText(self.TextPrizePool, _N(0))
    end
end

function P:evt_GetRoomDataRSP(msg)
	self:evt_refreshPrizePool()
    self:evt_TourRoomRankRefreshBRC()
end

function P:evt_TourRoomRankRefreshBRC()
    if GameModel.data.rank_list then
        for _, v in ipairs(GameModel.data.rank_list) do
            if v.brief.uid == PlayerModel:getUid() then
                bee.setText(self.TextRank, v.rank)
                return
            end
        end
    end
end

function P:evt_refreshBlind()
	local sb = GameModel.data:getSmallBlind()
	local bb = GameModel.data:getBigBlind()
    local ante = GameModel.data:getAnte()
	bee.setText(self.TextBlind, _T("LAB_FRIROOM_031") .. self:getBlindText(sb, bb, ante))

    self:evt_refreshNextBlind()
end

function P:evt_refreshNextBlind()
    local nextBlindInfo = GameModel.data:getNextBlindInfo()
    if not nextBlindInfo then
        bee.setText(self.TextBlindNext, _T("LAB_TOURNAMENT_SNG_INFO29"))
        self.BlindsInfo2:SetActive(false)
    else
	    bee.setText(self.TextBlindNext, _T("LAB_TOURNAMENT_SNG_INFO28") .. self:getBlindText(nextBlindInfo.small_blind, nextBlindInfo.big_blind, nextBlindInfo.ante))
        local dt = GameModel.data:getBlindUpTime()
        bee.setText(self.TextTime, TimeHelp:getTimeStrHMS(dt))
        self:once(1, function()
            self:evt_refreshNextBlind()
        end)
    end
end

function P:evt_SngSpinBRC()
end

function P:evt_BlindStatusBRC()
    self:evt_refreshBlind()
    self:evt_refreshPrizePool()
end

function P:evt_lan_mod()
    self:evt_refreshBlind()
    self:evt_refreshPrizePool()
    bee.setText(self.TextTitle, GameModel.data:getGameName())
end

