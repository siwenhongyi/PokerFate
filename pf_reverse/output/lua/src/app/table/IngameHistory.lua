local P = class("IngameHistory", UiDialog)

function P:onAwake()
    self.Panel = self:find("AnimRoot/Center/Panel")
    self.HistoryList = self:find("HistoryList", self.Panel)
    self.Content = self:find("Viewport/Content", self.HistoryList)
    self.Public = self:find("Public", self.Content)
    self.ImageCards = {
        self:find("ImageCard1", self.Public),
        self:find("ImageCard2", self.Public),
        self:find("ImageCard3", self.Public),
        self:find("ImageCard4", self.Public),
        self:find("ImageCard5", self.Public),
    }
    self.Item = self:find("item01", self.HistoryList)
    self.TextPage = self:find("TextPage", self.Panel)
    self.TextNoData = self:find("TextNoData", self.Panel)
    self.PageLastButton = self:find("PageLastButton", self.Panel)
    self.PageNextButton = self:find("PageNextButton", self.Panel)
    self.SaveButton = self:find("SaveButton", self.Public)

    self.Item:SetActive(false)
    self.Items = {}

    self.isSave = false
    self.SaveList = {}

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end, true)
    bee.addClick(self.PageLastButton, function()
        Game:playSound("ui_button_confirm")
        if self._showIndex > self._minIndex then
            self:setShowHand(self._showIndex - 1)
        end
    end)
    bee.addClick(self.PageNextButton, function()
        Game:playSound("ui_button_confirm")
        if self._showIndex < self._total then
            self:setShowHand(self._showIndex + 1)
        end
    end)

    Net:post("/collCard/list", {skip = 0}, function(data)
        if 0 == data.code then
            if data.list then
                for _,v in pairs(data.list) do
                    table.insert(self.SaveList, v.gameid)
                end
            end
        end
    end)
end

function P:onShow()
    self._index = 0
    self._total = 0
    self._showIndex = 0 -- 当前要显示的序号
    self._minIndex = 1  -- 最小可显示的序号
    self.Public:SetActive(false)
    for _, v in ipairs(self.Items) do
        v:SetActive(false)
    end
    self.TextPage:SetActive(false)
    self.TextNoData:SetActive(false)
    self:setShowHand(self._index)
    self:refreshArrow()
end

function P:refreshUI(info)
    local page, total = self._showIndex, self._total
    if self._total > 30 then
        total = 30
        page = 30 - (self._total - self._showIndex)
        self._minIndex = self._total - 30 + 1
    end
    bee.setText(self.TextPage, string.format("%d / %d", page, total))
    self.Public:SetActive(true)
    self.TextPage:SetActive(true)
    self.TextNoData:SetActive(false)
    for i = 1, 5 do
        bee.setIcon(self.ImageCards[i], GF.getCardImageByCode(info.board[i]))
    end
    local includeSelf = false
    for k, v in ipairs(info.hands) do
        local item = self.Items[k]
        if not item then
            item = CU.GameObject.Instantiate(self.Item, self.Content.transform, false)
            self.Items[#self.Items + 1] = item
        end
        item:SetActive(true)

        if not includeSelf then
            includeSelf = v.brief.uid == PlayerModel:getUid()
        end
        bee.setTextCut(self:find("TextName", item), v.brief.name, 230)
        bee.setText(self:find("Rank/TextLevel", item), v.brief.level)
        bee.setIcon(self:find("Rank/icon_rank_01", item), (tpl_level[v.brief.level] or tpl_level[1]).icon)
        GF.setTitleImage(self:find("ImageTitle", item), v.brief.title, true)
        GF.setFrameImage(self:find("ImageFrame", item), v.brief.frame)
        bee.setIcon(self:find("Mask/ImageIcon", item), PlayerModel:getAvatarIcon(v.brief.avatar))
        if (v.cards and #v.cards > 0) or v.hand_type <= 0 then
            bee.setText(self:find("TextCardType", item), _T(POKER_TYPE_NAME[v.hand_type]))
        else
            bee.setText(self:find("TextCardType", item), "")
        end
        local BgCard2 = self:find("BgCard2", item)
        local BgCard4 = self:find("BgCard4", item)
        local show_card_info = v.show_card_info or {}
        if not GameModel.data:isOmaha() then
            BgCard2:SetActive(true)
            BgCard4:SetActive(false)
            bee.setIcon(self:find("ImageCard1", BgCard2), GF.getCardImageByCode(v.cards[1]))
            bee.setIcon(self:find("ImageCard2", BgCard2), GF.getCardImageByCode(v.cards[2]))
            self:find("ImageCard1/EyeTag", BgCard2):SetActive(show_card_info[1] == 1)
            self:find("ImageCard2/EyeTag", BgCard2):SetActive(show_card_info[2] == 1)
        else
            BgCard2:SetActive(false)
            BgCard4:SetActive(true)
            local ImageCards = {
                self:find("ImageCard1", BgCard4),
                self:find("ImageCard2", BgCard4),
                self:find("ImageCard3", BgCard4),
                self:find("ImageCard4", BgCard4),
            }
            local cards, _ = PKHelper.getOmahaType(v.cards, info.board)
            local flag = false
            for i = 1, GameModel.data:getHandCardNum() do
                local c = v.cards[i]
                bee.setIcon(ImageCards[i], GF.getCardImageByCode(c))
                self:find("EyeTag", ImageCards[i]):SetActive(show_card_info[i] == 1)
                flag = false
                if cards then
                    for _, nc in ipairs(cards) do
                        if GF.getCardCode(nc) == c then
                            flag = true
                            break
                        end
                    end
                end
                self:find("BgWin", ImageCards[i]):SetActive(flag)
            end
        end
        local TextAdd, TextDec = self:find("TextAdd", item), self:find("TextDec", item)
        if v.profit > 0 then
            TextAdd:SetActive(true)
            TextDec:SetActive(false)
            bee.setText(TextAdd, "+" .. _N(v.profit))
        elseif v.profit == 0 then
            TextAdd:SetActive(false)
            TextDec:SetActive(true)
            bee.setText(TextDec, _N(v.profit))
        else
            TextAdd:SetActive(false)
            TextDec:SetActive(true)
            bee.setText(TextDec, "-" .. _N(-v.profit))
        end
    end
    for i = #info.hands + 1, #self.Items do
        self.Items[i]:SetActive(false)
    end

    self:saveEvent(includeSelf, info)
    self:refreshArrow()
end

function P:saveEvent(include, info)
    self.SaveButton:SetActive(include)
    if not include then
        return
    end

    self.isSave = false
    for _,v in pairs(self.SaveList) do
        if v == info.gameid then
            self.isSave = true
            break
        end
    end

    self:find("On", self.SaveButton):SetActive(self.isSave)
    bee.removeAllClick(self.SaveButton)
    bee.addClick(self.SaveButton, function()
        if self.isSave then
            Net:post("/collCard/update", {del_id = info.gameid}, function(d)
                if 0 == d.code then
                    self.isSave = not self.isSave
                    table.removebyvalue(self.SaveList, info.gameid)
                    GameModel:getReplayList()
                    -- PlayerModel:setCurRecord(table.nums(gameids))
                    self:find("On", self.SaveButton):SetActive(self.isSave)
                end
            end)
        else
            if PlayerModel:getCurRecord() >= PlayerModel:getRecordNum() then
                GameModel:getReplayList(function(data)
                    if 0 == data.code then
                        if data.list and #data.list > 0 then
                            UiManager:showTip({
                                text = _F("LAB_DEL_PLAYBACK_TIP5", GameModel:getReplayTitle(data.data)),
                                sureStr = _T("LAB_SAVE"),
                                cancelStr = _T("LAB_DEL_PLAYBACK_TIP6"),
                                onSure = function()
                                    self:changeReplay(data.data.gameid, info)
                                end,
                                onCancel = function()
                                end,
                            })
                        end
                    end
                end)
            else
                self:saveData(info)
            end
        end
    end)
end

function P:saveData(info)
    Net:post("/collCard/update", {add_id = info.gameid}, function(d)
        if 0 == d.code then
            self.isSave = not self.isSave
            table.insert(self.SaveList, info.gameid)
            PlayerModel:setCurRecord(#d.gameids)
            self:find("On", self.SaveButton):SetActive(self.isSave)
        end
    end)
end

function P:changeReplay(removeId, data)
    Net:post("/collCard/update", {del_id = removeId, add_id = data.gameid}, function(d)
        if 0 == d.code then
            self.isSave = not self.isSave
            table.insert(self.SaveList, data.gameid)
            PlayerModel:setCurRecord(#d.gameids)
            self:find("On", self.SaveButton):SetActive(self.isSave)
        end
    end)
end

function P:refreshArrow()
    self.PageLastButton:SetActive(self._showIndex > 1 and self._showIndex > self._total - 29)
    self.PageNextButton:SetActive(self._showIndex > 0 and self._showIndex < self._total)
end

function P:setShowHand(index)
    self._showIndex = index
    self:reqHand(index)
end

function P:reqHand(index)
    if 0 ~= index then
        local info = GameModel.data:getHandInfo(index)
        if info then
            self:refreshUI(info)
            return
        end
    end
    Net:sendReq("pb.GetHandsListREQ", {id = index})
end

function P:evt_GetHandsListRSP(msg)
    if 0 == msg.code then
        if self._total == 0 then
            self._total = msg.info.id
        end

         self._index = msg.info.id
        GameModel.data:setHandInfo(msg.info.id, msg.info)
        if 0 == self._showIndex or self._showIndex == self._index then
            self._showIndex = self._index
            self:refreshUI(msg.info)
        end

        -- Net:post("collCard/judge", {gameids = {msg.info.gameid}}, function(data)
        --     if data.code ~= 0 then return end
        --     if data.gameids ~= nil then
        --         for _,v in pairs(data.gameids) do
        --             if table.keyof(self.SaveList, v) == nil then
        --                 table.insert(self.SaveList, v)
        --             end
        --         end
        --     end

           
        -- end)   
    elseif tpl_RetCode.ERR_NO_MORE_DATA.code == msg.code then
        self.TextNoData:SetActive(true)
    end
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

