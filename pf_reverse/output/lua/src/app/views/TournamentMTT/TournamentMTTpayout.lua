local P = class("TournamentMTTpayout", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.panel2 = self:find("Center/panel2", self.AnimRoot)

    self.PiyoList = self:find("PiyoList", self.panel2)
    self.Content = self:find("Viewport/Content", self.PiyoList)

    self.BoxItem = self:find("BoxItem", self.Content)
    self.BoxItem:SetActive(false)
    self.ItemTitle = self:find("ItemTitle", self.BoxItem)
    self.Item = self:find("Item", self.PiyoList)
    self.Item:SetActive(false)

    self.Titles = {}
    self.TitlePoses = {}
    
    self.TitleOffset = 126.5

    bee.addClick(self:find("CloseButton", self.panel2), function()
        self:hideUI()
    end)

    bee.addClick(self:find("TITLE/infoButton", self.panel2), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonRules", {text = _T("LAB_TOURNAMENT_MTT_INFO52"), title = _T("LAB_TIP")})
    end)

    self._listWidth = self.PiyoList.transform.rect.width
end

function P:onShow()
    if self._params and self._params.data then
        Net:sendReq("pb.MttPotRewardStructureREQ", {tour_id = self._params.data.tour_id}, function(msg)
            if not bee.isNull(self.node) and msg and msg.reward_structure then
                self:setDatas(msg.reward_structure)
            end
        end)
    else
        local datas = {}
        for _, v in pairs(tpl_mtt_pot_reward_structure_list) do
            local d = {
                id = v.id,
                min_cnt = v.min_cnt,
                max_cnt = v.max_cnt,
                reward_list = json.decode(v.reward_structure),
            }
            for _, v in ipairs(d.reward_list) do
                v.rank_start, v.rank_end, v.rate = v[1], v[2], v[3]
            end
            table.insert(datas, d)
        end
        self:setDatas(datas)
    end
end

function P:setDatas(datas)
    local rows = {}
    local lines = {}
    for k, v in ipairs(datas) do
        table.insert(lines, v)
        if k % 10 == 0 then
            table.insert(rows, lines)
            lines = {}
        end
    end
    if #lines > 0 then
        table.insert(rows, lines)
    end

    for _, v in ipairs(rows) do
        self:setDatasBox(v)
    end
end

function P:setDatasBox(datas)
    table.sort(datas, function(a, b) return a.min_cnt > b.min_cnt end)

    local rows = {}
    for k, v in ipairs(datas) do
        for kk, vv in ipairs(v.reward_list) do
            if not rows[kk] then rows[kk] = {} end
            table.insert(rows[kk], vv)
        end
    end

    table.sort(datas, function(a, b) return a.min_cnt < b.min_cnt end)

    local BoxItem = CU.GameObject.Instantiate(self.BoxItem, self.Content.transform, false)
    BoxItem:SetActive(true)
    local ItemTitle = self:find("ItemTitle", BoxItem)

    self.Titles = {}
    self.TitlePoses = {}
    for k, v in ipairs(datas) do
        local n = self:find("TextNum" .. k, ItemTitle)
        if not n then
            n = CU.GameObject.Instantiate(self.Titles[1], ItemTitle.transform, false)
            n.transform.localPosition = bee.v3(self.TitleOffset + self.TitlePoses[k - 1].x, self.TitlePoses[k - 1].y)
        end
        table.insert(self.Titles, n)
        table.insert(self.TitlePoses, n.transform.localPosition)

        bee.setText(self.Titles[k], _F("{p1}-{p2}", v.min_cnt, v.max_cnt))
    end

    local n = #rows[1]
    for i, r in ipairs(rows) do
        local item = CU.GameObject.Instantiate(self.Item, BoxItem.transform, false)
        item:SetActive(true)

        local tournament_details_mtt_frame_list_horizontal = self:find("tournament_details_mtt_frame_list_horizontal", item)
        tournament_details_mtt_frame_list_horizontal:SetActive(i % 2 == 0)

        if r[1].rank_start == r[1].rank_end then
            bee.setText(self:find("TextRank", item), _F("#{p1}", r[1].rank_start))
        else
            bee.setText(self:find("TextRank", item), _F("#{p1}-#{p2}", r[1].rank_start, r[1].rank_end))
        end

        local TextNum = self:find("TextNum", item)
        
        for k = 1, n do
            local item = TextNum
            if r[n - k + 1] then
                if k > 1 then
                    item = CU.GameObject.Instantiate(TextNum, item.transform.parent, false)
                    item:SetActive(true)
                    item.transform.localPosition = bee.v3(self.TitlePoses[k].x, 0)
                end
                bee.setText(item, r[n - k + 1].rate / 10000)
            else
                TextNum:SetActive(false)
            end
        end
    end
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

return P