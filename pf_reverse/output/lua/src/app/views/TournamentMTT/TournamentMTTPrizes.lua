local P = class("TournamentMTTPrizes", UiBlurBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Right = self:find("Right", self.AnimRoot)

    self.SidePanel = self:find("SidePanel", self.Right)

    bee.addClick(self:find("TouchMask", self.AnimRoot), function()
        self:hideUI()
    end)
    bee.addClick(self:find("SideButton", self.SidePanel), function()
        self:hideUI()
    end)

    local RankList = self:find("Prizes/RankList", self.SidePanel)
    self.Item = self:find("Item", RankList)
    self.Item:SetActive(false)
    self.Items = {
        self:find("Item1", RankList),
        self:find("Item2", RankList),
        self:find("Item3", RankList),
        self:find("Item4", RankList),
    }
    for _, v in ipairs(self.Items) do
        v:SetActive(false)
    end
    self.ListRank = UiListEx:create(RankList)
    self.ListRank:setWidth(100)
    self.ListRank:setCreateFunc(function(data)
        if data.rank <= 3 then
            return CU.GameObject.Instantiate(self.Items[data.rank])
        end
        return CU.GameObject.Instantiate(self.Items[4])
    end)
    self.ListRank:setRefreshFunc(function(data, item)
        self:refreshRankItem(data, item)
    end)
end

function P:onShow()
    if self._params and self._params.data then
        Net:sendReq("pb.MttRankRewardREQ", {tour_id = self._params.data.tour_id}, function(resp)
            if not bee.isNull(self.node) and resp and resp.rank_reward_list then
                for _, v in ipairs(resp.rank_reward_list) do
                    v.__kind = v.rank <= 3 and 1 or 2
                end
                self.ListRank:setDatas(resp.rank_reward_list)
            end
        end)
    else
        self.ListRank:setDatas({
            {rank = 1, __kind = 1, reward_list = {{item_id = 10100001, item_num = 1000}}},
            {rank = 2, __kind = 1, reward_list = {{item_id = 10100001, item_num = 500}}},
            {rank = 3, __kind = 1, reward_list = {{item_id = 10100001, item_num = 300}}},
            {rank = 4, __kind = 2, reward_list = {{item_id = 10100001, item_num = 200}}},
            {rank = 5, __kind = 2, reward_list = {{item_id = 10100001, item_num = 100}}},
            {rank = 6, __kind = 2, reward_list = {{item_id = 10100001, item_num = 50}}},
            {rank = 7, __kind = 2, reward_list = {{item_id = 10100001, item_num = 25}}},
            {rank = 8, __kind = 2, reward_list = {{item_id = 10100001, item_num = 10}}},
        })
    end
end

function P:refreshRankItem(data, item)
    if data.rank >= 4 then
        local BgNums = self:find("BgNums", item)
        BgNums.transform.localScale = data.rank >= 1000 and bee.v3(0.6, 0.6, 0.6) or bee.v3one

        local rank = data.rank
        for i = 4, 1, -1 do
            if rank > 0 then
                self:find("Num_" .. i, BgNums):SetActive(true)
                local num = rank % 10
                bee.setIcon(self:find("Num_" .. i, BgNums), "Rankingslist[rankingslist_rank_number_" .. num .. "]")
                rank = math.floor(rank / 10)
            else
                self:find("Num_" .. i, BgNums):SetActive(false)
            end
        end
    end

    local BgItems = self:find("BgItems", item)
    local Content = self:find("ViewItems/Viewport/Content", item)
    self:removeAllChildren(BgItems)
    self:removeAllChildren(Content)
    if #data.reward_item_list >= 3 then
        BgItems = Content
        self:find("ViewItems", item):SetActive(true)
    else
        self:find("ViewItems", item):SetActive(false)
    end
    if data.reward_item_list then
        GF.addItemsToParent(BgItems, self.Item, data.reward_item_list, BgItems == Content and data or nil)
    end
end

function P:evt_uiBlur(flag, name)
    self:onUiBlur(flag, name)
end

return P