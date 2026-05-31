local P = class("TournamentMTTlist", UiFullView)

function P:onAwake()
    self.Panel = self:find("AnimRoot/Center/Panel")

    self.Items = {
        self:find("Item1", self.Panel),
        self:find("Item2", self.Panel),
        self:find("Item3", self.Panel),
    }
    self.Self = self:find("Self", self.Panel)
    self.Self:SetActive(false)

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)

    bee.addClick(self:find("Title/TextTitle/InfoButton", self.Panel), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("TournamentMTTpayout")
    end)

    local RankingsList = self:find("RankingsList", self.Panel)
    local Item1 = self:find("Item1", RankingsList)
    Item1:SetActive(false)
    
    self.ListRankings = UiListEx:create(RankingsList)
    self.ListRankings:setWidth(190)
    self.ListRankings:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(Item1)
    end)
    self.ListRankings:setRefreshFunc(function(data, item)
        self:refreshRankItem(data, item)
    end)
    self.ListRankings:addValueChanged(function()
        if self._selfData and self.ListRankings:isDataShowing(self._selfData) then
            self.Self:SetActive(false)
        else
            self.Self:SetActive(true)
        end
    end)
    self.ListRankings:setTopBottom(0, 100)
end

function P:onShow()
    if self._params and self._params.data then
        Net:sendReq("pb.MttRankREQ", {tour_id = self._params.data.tour_id}, function(resp)
            if not bee.isNull(self.node) and resp and resp.rank_list then
                for _, v in ipairs(resp.rank_list) do
                    v.__kind = v.rank <= 3 and 1 or 2
                end
                self:setDatas(resp.rank_list)
            end
        end)
    else
        self:setDatas({
            {rank = 1, __kind = 1, chips = 50, brief = {uid = PlayerModel:getUid(), name = PlayerModel:getName()}, reward_item_list = {{item_id = 10100001, item_num = 1000}}},
            {rank = 2, __kind = 1, chips = 75, brief = {uid = 1, name = PlayerModel:getName()}},
            {rank = 3, __kind = 1, chips = 100, brief = {uid = 2, name = PlayerModel:getName()}},
            {rank = 4, __kind = 2, chips = 150, brief = {uid = 3, name = PlayerModel:getName()}},
            {rank = 5, __kind = 2, chips = 200, brief = {uid = 4, name = PlayerModel:getName()}},
            {rank = 6, __kind = 2, chips = 300, brief = {uid = 5, name = PlayerModel:getName()}},
            {rank = 7, __kind = 2, chips = 400, brief = {uid = 6, name = PlayerModel:getName()}},
            {rank = 8, __kind = 2, chips = 500, brief = {uid = 7, name = PlayerModel:getName()}},
        })
    end
end

function P:setDatas(datas)
    self.Self:SetActive(false)
    for _, v in ipairs(datas) do
        if v.brief.uid == PlayerModel:getUid() then
            self._selfData = v
            self:refreshRankItem(v, self.Self)
            break
        end
    end
    self.ListRankings:setDatas(datas)
end

function P:refreshRankItem(data, item)
    local Frame = self:find("Frame", item)
    local Rank = self:find("Rank", item)
    local curRank = data.rank_start or data.rank
    if Frame then
        self:find("rankingslist_player_tab_01", Frame):SetActive(1 == curRank)
        self:find("rankingslist_player_tab_02", Frame):SetActive(2 == curRank)
        self:find("rankingslist_player_tab_03", Frame):SetActive(3 == curRank)
        self:find("rankingslist_player_tab_04", Frame):SetActive(4 <= curRank)
    end
    self:find("rankingslist_rank_icon_01", Rank):SetActive(1 == curRank)
    self:find("rankingslist_rank_icon_02", Rank):SetActive(2 == curRank)
    self:find("rankingslist_rank_icon_03", Rank):SetActive(3 == curRank)
    self:find("Number", Rank):SetActive(4 <= curRank)

    if curRank >= 4 then
        local Number = self:find("Number", Rank)
        Number.transform.localScale = curRank >= 1000 and bee.v3(0.6, 0.6, 0.6) or bee.v3one
        
        for i = 4, 1, -1 do
            if curRank > 0 then
                self:find("Num_" .. i, Number):SetActive(true)
                local num = curRank % 10
                bee.setIcon(self:find("Num_" .. i, Number), "Rankingslist[rankingslist_rank_number_" .. num .. "]")
                curRank = math.floor(curRank / 10)
            else
                self:find("Num_" .. i, Number):SetActive(false)
            end
        end
    end

    if data.reward_item_list and #data.reward_item_list > 0 then
        local Reward = self:find("Reward", item)
        Reward:SetActive(true)
        local Item01 = self:find("Item", Reward)
        Item01:SetActive(false)
        local BgItems = self:find("BgItems", Reward)
        local ViewItems = self:find("ViewItems", Reward)
        local Content = self:find("ViewItems/Viewport/Content", Reward)
        self:removeAllChildren(BgItems)
        self:removeAllChildren(Content)
        
        local autoScroll = false
        if #data.reward_item_list > 3 then
            BgItems = Content
            ViewItems:SetActive(true)
            autoScroll = true
        else
            ViewItems:SetActive(false)
        end
        GF.addItemsToParent(BgItems, Item01, data.reward_item_list, autoScroll and data or nil)
    else
        self:find("Reward", item):SetActive(false)
    end
    local Information = self:find("Information", item)
    GF.setFrameImage(self:find("Avatar/ImageFrame", Information), data.brief.frame)
    GF.setTitleImage(self:find("ImageTitle", Information), data.brief.title)
    bee.setText(self:find("TextName", Information), data.brief.name)
    bee.setIcon(self:find("Avatar/avatar_frame_01_mask/ImageIcon", Information), PlayerModel:getAvatarIcon(data.brief.avatar))
    
    bee.addClick(self:find("Avatar", Information), function()
        Game:playSound("ui_button_confirm")
        if data.brief.uid == PlayerModel:getUid() then
            UiManager:showUI("InformationMainNew", {from = "Ranking"})
        else
            UiManager:showUI("InformationMainNew", {uid = data.brief.uid, from = "Ranking"})
        end
    end, true)
end

return P