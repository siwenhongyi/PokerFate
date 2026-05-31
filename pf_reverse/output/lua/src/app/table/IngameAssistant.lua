local P = class("IngameAssistant", UiDialog)

function P:onAwake()
    self.Left = self:find("AnimRoot/Left")

    self.Empty = self:find("Empty", self.Left)

    self.PotList = self:find("PotList", self.Left)
    self.PotContent = self:find("Viewport/Content", self.PotList)
    self.MainPot = self:find("MainPot", self.PotList)
    self.MainPot:SetActive(false)
    self.PotItem = self:find("Item1", self.MainPot)
    self.PotItem:SetActive(false)

    self.DetailsList = self:find("DetailsList", self.Left)
    self.DetailsContent = self:find("Viewport/Content", self.DetailsList)
    self.PreFlop = self:find("PreFlop", self.DetailsList)
    self.PreFlop:SetActive(false)
    self.Flop = self:find("Flop", self.DetailsList)
    self.Flop:SetActive(false)
    self.Showdown = self:find("Showdown", self.DetailsList)
    self.Showdown:SetActive(false)

    self.Item1 = self:find("Item1", self.DetailsList)
    self.Item1:SetActive(false)
    self.ShowItem = self:find("Item1", self.Showdown)
    self.ShowItem:SetActive(false)

    local Tabs = {
        self:find("Tab/Details", self.Left),
        self:find("Tab/Pot", self.Left),
    }

    for k, v in ipairs(Tabs) do
        bee.onCheck(v, function(isOn)
            if isOn then
                self._showIndex = k
                self:refreshShowView()
                bee.logEvent("ingame-helper-tab", GameModel.data:getGameType(), GameModel.data:getRoomId(), k, GameModel.data:getGameId())
            end
        end)
    end

    bee.addClick(self:find("CloseButton", self.Left), function()
        self:hideUI()
    end)

    bee.addClick2(self:find("Mask"), function()
        self:hideUI()
    end)
end

function P:onShow()
    self.transform.localPosition = bee.v3zero
    self._showIndex = 1
    if self._params and self._params.data then
        local data = self._params.data
        self._game_type = data.game_type
        self._data = {
            round_rd = {},
            pool_rd = {},
            show_round_rd = { 
                pot = 0,
                items = {},
            },
        }
        self._users = {}
        for _, v in ipairs(data.user) do
            self._users[v.uid] = v
            v.left_hand_chips = v.begin_chips
        end
        local board = {}
        local isAllAllin, totalBet, totalPot = false, 0, 0
        local startSeatid = 1
        for _, v in ipairs(data.round) do
            if v.board then
                for _, c in ipairs(v.board) do
                    table.insert(board, c)
                end
            end
            table.insert(self._data.round_rd, {
                stage = tonumber(v.stage),
                pot = 0,
                board = clone(board),
                action = v.action,
            })

            for _, a in ipairs(v.action) do
                local player = self._users[a.uid]
                if player then
                    player.left_hand_chips = player.left_hand_chips - (a.action_chips or 0)
                    a.left_hand_chips = player.left_hand_chips
                end
                totalBet = totalBet + (a.action_chips or 0)
                if a.action_type == POKER_ACTION.SB then
                    startSeatid = a.seatid
                end
            end

            self._data.round_rd[#self._data.round_rd].pot = self._data.show_round_rd.pot
            self._data.show_round_rd.pot = 0
            self._data.pool_rd = {}
            totalPot = 0
            for _, pot in ipairs(v.pool) do
                local d = {
                    poolid = pot.poolid,
                    pot = pot.pot + pot.fee,
                    users = pot.user,
                }
                totalPot = totalPot + d.pot
                self._data.show_round_rd.pot = self._data.show_round_rd.pot + d.pot
                
                if d then
                    table.insert(self._data.pool_rd, d)
                end
            end

            if totalBet - totalPot > 0 then
                local backChips = totalBet - totalPot
                local seatid, maxActionChips = -1, 0
                for _, act in ipairs(v.action) do
                    if act.action_chips > maxActionChips then
                        maxActionChips = act.action_chips
                        seatid = act.seatid
                    end
                end
                if seatid >= 0 and backChips > 0 then
                    local u = self._users[self:getUid(seatid)]
                    if u then
                        u.left_hand_chips = (u.left_hand_chips or 0) + backChips
                    end
                end
                totalBet = totalPot
            end
        end
        
        if data.show_hand_info and #data.show_hand_info > 0 then
            for _, v in ipairs(data.show_hand_info) do
                table.insert(self._data.show_round_rd.items, {
                    seatid = v.seatid,
                    uid = self:getUid(v.seatid),
                    hand_type = 0,
                    profit = 0,
                    hand_cards = v.hand_card,
                    show_type_list = {1,1,1,1,1,1},
                })
            end
        end
        -- 添加胜利信息
        for _, v in ipairs(data.winning_info) do
            local flag = true
            for _, item in ipairs(self._data.show_round_rd.items) do
                if item.uid == v.uid then
                    item.profit = v.chips
                    flag = false
                    break
                end
            end
            if flag then
                table.insert(self._data.show_round_rd.items, {
                    seatid = v.seatid,
                    uid = v.uid,
                    hand_type = 0,
                    profit = v.chips,
                    hand_cards = {},
                    show_type_list = {1,1,1,1,1,1},
                })
            end
        end
        -- 添加弃牌玩家盈亏信息
        for _, v in pairs(self._users) do
            local flag = true
            for _, item in ipairs(self._data.show_round_rd.items) do
                if item.uid == v.uid then
                    item.profit = item.profit - (v.begin_chips - v.left_hand_chips)
                    flag = false
                    if item.uid == PlayerModel:getUid() and #item.hand_cards == 0 then
                        item.hand_cards = v.hand_card
                    end
                    item.show_type_list = v.show_type_list or {1,1,1,1,1,1}
                    break
                end
            end
            if flag then
                local d = {
                    seatid = v.seatid,
                    uid = v.uid,
                    hand_type = -1,
                    profit = v.left_hand_chips - v.begin_chips,
                    hand_cards = v.uid == PlayerModel:getUid() and v.hand_card or {},
                    show_type_list = v.show_type_list or {1,1,1,1,1,1},
                }
                if v.show_type_list and v.uid ~= PlayerModel:getUid() then
                    for sk, sv in ipairs(v.show_type_list) do
                        if sv == 2 then
                            d.hand_cards[sk] = v.hand_card[sk] or 0
                        else
                            d.hand_cards[sk] = 0
                        end
                    end
                end
                table.insert(self._data.show_round_rd.items, d)
            end
        end
        local n = #self._data.show_round_rd.items
        table.sort(self._data.show_round_rd.items, function(a, b)
            local i1, i2 = a.seatid - startSeatid, b.seatid - startSeatid
            if i1 < 0 then i1 = i1 + n end
            if i2 < 0 then i2 = i2 + n end
            return i1 < i2
        end)
        self._inGame = false
    elseif GameModel.data then
        self._data = GameModel.data:getHistoryDetail()
        self._game_type = GameModel.data:getGameType()
        self._inGame = true
    else
        self._data = nil
    end

    self:refreshUI()
end

function P:refreshUI()
    self._curFlop = nil
    self._curBoard = nil

    self:removeAllChildren(self.PotContent.transform)
    self:removeAllChildren(self.DetailsContent.transform)
    if self._data then
        for _, v in ipairs(self._data.round_rd) do
            self:addRoundNode(v)
        end
        if self._data.show_round_rd.pot > 0 then
            self:addShowdownNode(self._data.show_round_rd)
        end
        for _, v in ipairs(self._data.pool_rd) do
            self:addPotNode(v)
        end
    end

    self:refreshShowView()
end

function P:refreshShowView()
    self.Empty:SetActive(not self._data)
    if self._inGame and not GameModel.data:isPlaying() then
        self.Empty:SetActive(true)
    end
    self.DetailsList:SetActive(not self.Empty.activeSelf and self._showIndex == 1)
    self.PotList:SetActive(not self.Empty.activeSelf and self._showIndex == 2)
end

function P:addPreFlopNode(data)
    local item = CU.GameObject.Instantiate(self.PreFlop, self.DetailsContent.transform, false)
    item:SetActive(true)

    self._curFlop = item
    if self._data.ante_rd and self._data.ante_rd.action then
        for _, v in ipairs(self._data.ante_rd.action) do
            self:addActionItem(v)
        end
    end
    for _, v in ipairs(data.action) do
        self:addActionItem(v)
    end
end

function P:addRoundNode(data)
    if data.stage == POKER_ROUND.PRE_FLOP then
        self:addPreFlopNode(data)
    else
        local item = CU.GameObject.Instantiate(self.Flop, self.DetailsContent.transform, false)
        item:SetActive(true)
        
        self._curFlop = item

        local Title = self:find("Title", item)
        bee.setText(self:find("TextTitle", Title), _T(POKER_ROUND_NAME[data.stage]))
        bee.setText(self:find("TextPot", Title), self:getBetChipsStr(data.pot))

        local board = data.board
        if not data.board and self._inGame then
            board = {}
            local num = data.stage == POKER_ROUND.FLOP and 3 or (data.stage == POKER_ROUND.TURN and 4 or 5)
            for k, v in ipairs(GameModel.data:getBoardInfo()) do
                if k <= num then
                    board[k] = v
                else
                    break
                end
            end
            data.board = board
        end
        self._curBoard = board
        for i = 1, 5 do
            if board[i] and board[i] > 0 then
                bee.setIcon(self:find("BoradCards/Card/Card" .. i, Title), GF.getCardImageByCode(board[i]))
            else
                self:find("BoradCards/Card/Card" .. i, Title):SetActive(false)
            end
        end
        for _, v in ipairs(data.action) do
            self:addActionItem(v)
        end
    end
end

function P:addActionItem(data)
    local actionItem = CU.GameObject.Instantiate(self.Item1, self._curFlop.transform, false)
    actionItem:SetActive(true)
    self:refreshActionItem(data, actionItem)
end

function P:addShowdownNode(data)
    local item = CU.GameObject.Instantiate(self.Showdown, self.DetailsContent.transform, false)
    item:SetActive(true)

    bee.setText(self:find("Title/TextPot", item), self:getBetChipsStr(data.pot))

    for _, v in ipairs(data.items) do
        local showItem = CU.GameObject.Instantiate(self.ShowItem, item.transform, false)
        showItem:SetActive(true)
        self:refreshShowItem(v, showItem)
    end
end

function P:addPotNode(data)
    local item = CU.GameObject.Instantiate(self.MainPot, self.PotContent.transform, false)
    item:SetActive(true)

    bee.setText(self:find("Title/TextTitle", item), 0 == data.poolid and _T("LAB_GAME_068") or (_F("LAB_GAME_069", data.poolid)))
    bee.setText(self:find("Title/TextPot", item), self:getBetChipsStr(data.pot))

    for _, v in ipairs(data.users) do
        local potItem = CU.GameObject.Instantiate(self.PotItem, item.transform, false)
        potItem:SetActive(true)
        self:refreshPotItem(v, potItem)
    end
end

function P:refreshActionItem(data, item)
    bee.setTextCut(self:find("TextName", item), self:getName(data), 176)
    bee.setText(self:find("Balance/TextChip", item), self:getBetChipsStr(data.left_hand_chips or 0))
    bee.setIcon(self:find("Action/ImageTag", item), POKER_RECORD_TAGS[data.action_type])
    bee.setText(self:find("Action/TextAction", item), _T(POKER_ACTION_TAGS[data.action_type].name))
    if data.action_chips and data.action_chips > 0 then
        bee.setText(self:find("Action/TextChip", item), self:getBetChipsStr(data.action_chips))
    else
        bee.setText(self:find("Action/TextChip", item), "-")
    end
    self:find("ingame_assistant_detailes_action_bg_03", item):SetActive(data.uid == PlayerModel:getUid())
end

function P:refreshShowItem(data, item)
    bee.setTextCut(self:find("TextName", item), self:getName(data), 176)
    local cards, cardType = nil, nil
    if not data.hand_type or data.hand_type == 0 then
        if not data.hand_cards or #data.hand_cards == 0 then
            if data.profit <= 0 then
                bee.setText(self:find("TextCardType", item), _T(POKER_TYPE_NAME[-1]))
            else
                bee.setText(self:find("TextCardType", item), "")
            end
        else
            cards, cardType = PKHelper.getCardType2(data.hand_cards, self._curBoard or {}, self._game_type)
            bee.setText(self:find("TextCardType", item), _T(cardType))
            if cards then
                for k, v in ipairs(cards) do
                    cards[k] = GF.getCardCode(v.number, v.color)
                end
            end
        end
    else
        bee.setText(self:find("TextCardType", item), _T(POKER_TYPE_NAME[data.hand_type]))
    end
    if data.profit > 0 then
        bee.setText(self:find("TextWin", item), "+" .. self:getBetChipsStr(data.profit))
    elseif data.profit < 0 then
        bee.setText(self:find("TextLose", item), self:getBetChipsStr(data.profit))
    else
        bee.setText(self:find("TextWin", item), "0")
    end
    local cardParent = nil
    if self:isOmaha() then
        cardParent = self:find("HoleCards/OMH", item)
        self:find("HoleCards/PK", item):SetActive(false)
    else
        cardParent = self:find("HoleCards/PK", item)
        self:find("HoleCards/OMH", item):SetActive(false)
    end
    cardParent:SetActive(true)
    
    local num = self:isOmaha() and 4 or 2
    for i = 1, num do
        local v = data.hand_cards and data.hand_cards[i] or 0
        local card = self:find("Card" .. i, cardParent)
        bee.setIcon(card, GF.getCardImageByCode(v))
        if v > 0 then
            if cards and table.indexof(cards, v) > 0 then
                bee.setColor(card, COLOR.main_white)
            else
                bee.setColor(card, COLOR.main_grey)
            end
            self:find("ingame_assistant_details_icon_show", card):SetActive(data.show_type_list[i] == 2)
        else
            self:find("ingame_assistant_details_icon_show", card):SetActive(false)
        end
    end
    
    for i = 1, 5 do
        local card = self:find("BoradCards/Card/Card" .. i, item)
        if cards and self._curBoard and self._curBoard[i] and self._curBoard[i] > 0 then
            bee.setIcon(card, GF.getCardImageByCode(self._curBoard[i]))
            if cards and table.indexof(cards, self._curBoard[i]) > 0 then
                bee.setColor(card, COLOR.main_white)
            else
                bee.setColor(card, COLOR.main_grey)
            end
        else
            card:SetActive(false)
        end
    end
    self:find("ingame_assistant_detailes_action_bg_03", item):SetActive(data.uid == PlayerModel:getUid())
end

function P:refreshPotItem(data, item)
    bee.setTextCut(self:find("TextName", item), self:getName(data), 176)
    bee.setText(self:find("TextPot", item), self:getBetChipsStr(data.chips))
    self:find("ingame_assistant_detailes_action_bg_03", item):SetActive(data.uid == PlayerModel:getUid())
end

function P:getBetChipsStr(chips)
    if not self._inGame then
        return _N(chips)
    end
    return GameModel.data:getBetChipsStr(chips)
end

function P:getUid(seatid)
    if self._users then
        for _, v in pairs(self._users) do
            if v.seatid == seatid then
                return v.uid
            end
        end
    end
    return 0
end

function P:getName(data)
    if data.name and data.name ~= "" then
        return data.name
    end
    if self._users and self._users[data.uid] then
        return self._users[data.uid].name
    end
    if self._inGame then
        local info, i = GameModel.data:getPlayerByUid(data.uid)
        if info then
            return info.name
        end
    end
    return ""
end

function P:isOmaha()
    return GF.isOmahaGame(self._game_type)
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

function P:evt_DealerInfoRSP()
    if not self._inGame then return end

    self._curFlop = nil
    self._curBoard = nil
    self:refreshShowView()
    self:removeAllChildren(self.PotContent.transform)
    self:removeAllChildren(self.DetailsContent.transform)

    self._data = GameModel.data:getHistoryDetail()
    -- self.DetailsList:GetComponent("ScrollRect").verticalNormalizedPosition = 0
end

function P:evt_ActionBRC()
    if not self._inGame then return end

    local rd = self._data.round_rd[#self._data.round_rd]
    if not rd then return end
    local action = rd.action
    if action and #action > 0 then
        self:addActionItem(action[#action])
        self._curFlop:SetActive(true)
    end
    -- self:once(0.2, function()
    --     self.DetailsList:GetComponent("ScrollRect").verticalNormalizedPosition = 0
    -- end)
end

function P:evt_RoundStartBRC()
    if not self._inGame then return end
    
    local rd = self._data.round_rd[#self._data.round_rd]
    if rd then
        self:addRoundNode(rd)
        self._curFlop:SetActive(false)
    end
    -- self:once(0.2, function()
    --     self.DetailsList:GetComponent("ScrollRect").verticalNormalizedPosition = 0
    -- end)
end

function P:evt_assistant_show_board()
    if not bee.isNull(self._curFlop) then
        self._curFlop:SetActive(true)
    end
end

function P:evt_RoundOverBRC()
    if not self._inGame then return end

    self:removeAllChildren(self.PotContent.transform)
    for _, v in ipairs(self._data.pool_rd) do
        self:addPotNode(v)
    end
    -- self:once(0.2, function()
    --     self.PotList:GetComponent("ScrollRect").verticalNormalizedPosition = 1
    -- end)
end

function P:evt_WinnerRSP()
    if not self._inGame then return end

    self:addShowdownNode(self._data.show_round_rd)

    -- self:once(0.2, function()
    --     self.DetailsList:GetComponent("ScrollRect").verticalNormalizedPosition = 0
    -- end)
end

function P:evt_TableGameOverRSP()
    if not self._inGame then return end

    self._data = GameModel.data:getHistoryDetail()
    self:refreshShowView()
end

function P:evt_GetRoomDataRSP()
    if not self._inGame then return end

    self._data = GameModel.data:getHistoryDetail()
    self:refreshUI()
end
function P:evt_refreshShowBB()
    if not self._inGame then return end

    self:refreshUI()
end

return P