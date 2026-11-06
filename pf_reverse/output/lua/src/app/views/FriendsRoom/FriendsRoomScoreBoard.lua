local P = class("FriendsRoomScoreBoard", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)
    self.TextTitle = self:find("TextTitle", self.Panel)
    
    self.PiyoList = self:find("PiyoList", self.Panel)
    self.Item1 = self:find("Item1", self.PiyoList)
    self.Item1:SetActive(false)
    self.Item2 = self:find("Item2", self.PiyoList)
    self.Item2:SetActive(false)

    self.Title01 = self:find("Title01", self.Panel)
    self.Title02 = self:find("Title02", self.Panel)
    self.TextTime = self:find("TextTime", self.Panel)
    self.Empty = self:find("Empty", self.Panel)

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)

    self.ListHistory = UiListEx:create(self.PiyoList)
    self.ListHistory:setWidth(170)
    self.ListHistory:setCreateFunc(function(data)
        if self._isSNG then
            return CU.GameObject.Instantiate(self.Item2)
        end
        return CU.GameObject.Instantiate(self.Item1)
    end)
    self.ListHistory:setRefreshFunc(function(data, item)
        self:refreshItem(data, item)
    end)

    self._ranksImg = {
        "Rankingslist[rankingslist_rank_icon_01]",
        "Rankingslist[rankingslist_rank_icon_02]",
        "Rankingslist[rankingslist_rank_icon_03]",
        "Rankingslist[rankingslist_rank_number_4]",
        "Rankingslist[rankingslist_rank_number_5]",
        "Rankingslist[rankingslist_rank_number_6]",
    }
end

function P:onShow()
    self._isSNG = false
    if GameModel.data then
        self._isSNG = GameModel.data:isFriendSNG()
        Net:sendReq("pb.GetScoreboardREQ", {setid = "", roomid = GameModel.data:getRoomId(), game_type = GameModel.data:getGameType()})

        if self._isSNG then
            bee.setText(self.TextTitle, _F("LAB_FRIROOM_059", GameModel.data:getSeatNum()))
        else
            bee.setText(self.TextTitle, GF.getGameTypeName(GameModel.data:getGameType()) .. " " .. _N(GameModel.data:getSmallBlind()) .. "/" .. _N(GameModel.data:getBigBlind()))
        end
    else
        self._isSNG = GF.isFriendSNG(self._params.data.game_type)
        Net:sendReq("pb.GetScoreboardREQ", {setid = self._params.data.setid, roomid = self._params.data.roomid, game_type = self._params.data.game_type})
        
        if self._isSNG then
            bee.setText(self.TextTitle, _F("LAB_FRIROOM_059", self._params.data.seat_num))
        else
            bee.setText(self.TextTitle, GF.getGameTypeName(self._params.data.game_type) .. " " .. _N(self._params.data.bb / 2) .. "/" .. _N(self._params.data.bb))
        end
    end
    
    self.Title01:SetActive(not self._isSNG)
    self.Title02:SetActive(self._isSNG)

    -- ============ 测试数据 (测试完删除) ============
    -- local testInfos
    -- if self._isSNG then
    --     -- SNG模式: 只需要 name/avatar/frame/rank
    --     testInfos = {
    --         {name="Alice",   avatar=1,  frame=1, rank=1},
    --         {name="Bob",     avatar=2,  frame=2, rank=2},
    --         {name="Charlie", avatar=3,  frame=3, rank=3},
    --         {name="David",   avatar=4,  frame=1, rank=4},
    --         {name="Eve",     avatar=5,  frame=2, rank=5},
    --         {name="Frank",   avatar=6,  frame=3, rank=6},
    --     }
    -- else
    --     -- 非SNG模式: name/avatar/frame/hands/profit
    --     testInfos = {
    --         {name="Alice",   avatar=1,  frame=1, hands=45, profit=15000},
    --         {name="Bob",     avatar=2,  frame=2, hands=38, profit=-5000},
    --         {name="Charlie", avatar=3,  frame=3, hands=52, profit=32000},
    --         {name="David",   avatar=4,  frame=1, hands=30, profit=-12000},
    --         {name="Eve",     avatar=5,  frame=2, hands=41, profit=8000},
    --         {name="Frank",   avatar=6,  frame=3, hands=36, profit=0},
    --     }
    -- end
    -- self:evt_GetScoreboardRSP({end_time = os.time() - 3600, infos = testInfos})
    -- ============ 测试数据结束 ============
end

function P:refreshItem(data, item)
    bee.setTextCut(self:find("TextName", item), data.name, 190)
    bee.setIcon(self:find("Avatar/Mask/ImageIcon", item), PlayerModel:getAvatarIcon(data.avatar))
    GF.setFrameImage(self:find("Avatar/ImageFrame", item), data.frame)

    if self._isSNG then 
        bee.setIcon(self:find("rankingslist_rank_icon_01", item), self._ranksImg[data.rank], true)
    else
        bee.setText(self:find("TextHands", item), data.hands)
        if data.profit > 0 then
            bee.setText(self:find("TextWin", item), "+" .. data.profit)
            bee.setText(self:find("TextLose", item), "")
        else
            bee.setText(self:find("TextWin", item), "")
            bee.setText(self:find("TextLose", item), data.profit)
        end
    end
end

function P:evt_GetScoreboardRSP(msg)
    if msg.end_time > 0 then
        local txt = _T("LAB_FRIROOM_064") .. TimeHelp:getDateTimeStr(msg.end_time)
        if msg.offline_room_over then
            txt = txt .. " " .. _T("LAB_FRIROOM_080")
        end
        bee.setText(self.TextTime, txt)
    else
        bee.setText(self.TextTime, "")
    end

    self.ListHistory:setDatas(msg.infos)
    self.Empty:SetActive(0 == #msg.infos)
end

return P