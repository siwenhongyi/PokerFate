local P = class("TournamentMTTRanks", UiBase)

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

    local RankList = self:find("Rank/RankList", self.SidePanel)
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
        Net:sendReq("pb.MttRankREQ", {tour_id = self._params.data.tour_id}, function(resp)
            if not bee.isNull(self.node) and resp and resp.rank_list then
                for _, v in ipairs(resp.rank_list) do
                    v.__kind = v.rank <= 3 and v.rank or 4
                end
                self.ListRank:setDatas(resp.rank_list)
            end
        end)
    else
        self.ListRank:setDatas({
            {rank = 1, __kind = 1, chips = 50, brief = {uid = PlayerModel:getUid(), name = PlayerModel:getName()}},
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

function P:refreshRankItem(data, item)
    bee.setTextCut(self:find("Name", item), GF.getOtherName(data.brief.name, nil, data.brief.uid), 230)
    bee.setText(self:find("TextChips", item), _N(data.chips))
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

    self:find("tournament_ingame_rank_frame_04", item):SetActive(data.brief.uid == PlayerModel:getUid())
end

return P