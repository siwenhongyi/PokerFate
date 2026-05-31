local P = class("TournamentMTTpayout", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.panel2 = self:find("Center/panel2", self.AnimRoot)

    self.PiyoList = self:find("PiyoList", self.panel2)
    self.Content = self:find("Viewport/Content", self.PiyoList)

    self.Vertical = self:find("Vertical", self.Content)
    self.ItemTitle = self:find("ItemTitle", self.Content)
    self.Item = self:find("Item", self.PiyoList)
    self.Item:SetActive(false)

    self.Titles = {}
    self.TitlePoses = {}
    self.VerticalBgs = {self:find("tournament_details_mtt_frame_list_vertical", self.Vertical)}
    self.TitleOffset = 126.5
    for i = 1, 20 do
        local n = self:find("TextNum" .. i, self.ItemTitle)
        if n then
            table.insert(self.Titles, n)
            table.insert(self.TitlePoses, n.transform.localPosition)

            n:SetActive(false)
        else
            break
        end
    end

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
    -- if self._params and self._params.data then
    --     Net:sendReq("pb.MttPotRewardStructureREQ", {tour_id = self._params.tour_id}, function(msg)
    --         if not bee.isNull(self.node) and msg and msg.reward_structure then
    --             self:setDatas(msg.reward_structure)
    --         end
    --     end)
    -- else
        -- self:setDatas({
        --     {min_cnt = 3, max_cnt = 10, reward_list = {{rank_start = 1, rank_end = 1, rate = 7000}, {rank_start = 2, rank_end = 2, rate = 3000}}},
        --     {min_cnt = 11, max_cnt = 20, reward_list = {{rank_start = 1, rank_end = 1, rate = 5000}, {rank_start = 2, rank_end = 2, rate = 3000}, {rank_start = 3, rank_end = 3, rate = 2000}}},
        --     {min_cnt = 21, max_cnt = 30, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        --     -- {min_cnt = 31, max_cnt = 40, reward_list = {{rank_start = 1, rank_end = 1, rate = 3700}, {rank_start = 2, rank_end = 2, rate = 2500}, {rank_start = 3, rank_end = 3, rate = 1500}, {rank_start = 4, rank_end = 4, rate = 1200}, {rank_start = 5, rank_end = 5, rate = 1100}}},
        -- })
    -- end
    local datas = {}
    for _, v in pairs(tpl_mtt_pot_reward_structure_list) do
        table.insert(datas, {
            id = v.id,
            min_cnt = v.min_cnt,
            max_cnt = v.max_cnt,
            reward_list = json.decode(v.reward_structure),
        })
    end
    self:setDatas(datas)
end

function P:setDatas(datas)
    table.sort(datas, function(a, b) return a.min_cnt > b.min_cnt end)

    local rows = {}
    local width = self._listWidth / 2 + self.Titles[1].transform.localPosition.x - self.TitleOffset / 2
    for k, v in ipairs(datas) do
        width = width + self.TitleOffset
        if not self.Titles[k] then
            self.Titles[k] = CU.GameObject.Instantiate(self.Titles[1], self.ItemTitle.transform, false)
            local pos = self.TitlePoses[#self.Titles - 1]
            pos = bee.v3(pos.x + self.TitleOffset, pos.y, pos.z)
            self.Titles[k].transform.localPosition = pos
            self.TitlePoses[k] = pos
        end
        if k > 1 and k % 2 == 1 then
            local bg = CU.GameObject.Instantiate(self.VerticalBgs[1], self.Vertical.transform, false)
            local pos = self.VerticalBgs[#self.VerticalBgs].transform.localPosition
            table.insert(self.VerticalBgs, bg)
            pos.x = pos.x + self.TitleOffset * 2
            bg.transform.localPosition = pos
        end
        if self.Titles[k] then
            bee.setText(self.Titles[k], _F("{p1}-{p2}", v.min_cnt, v.max_cnt))
            self.Titles[k]:SetActive(true)
        end
        for kk, vv in ipairs(v.reward_list) do
            if not rows[kk] then rows[kk] = {} end
            table.insert(rows[kk], vv)
        end
    end
    if width > self._listWidth then
        local s = self.Content.transform.sizeDelta
        s.x = width
        self.Content.transform.sizeDelta = s
    end

    for i, r in ipairs(rows) do
        local item = CU.GameObject.Instantiate(self.Item, self.Content.transform, false)
        item:SetActive(true)

        local tournament_details_mtt_frame_list_horizontal = self:find("tournament_details_mtt_frame_list_horizontal", item)
        tournament_details_mtt_frame_list_horizontal:SetActive(i % 2 == 0)
        if i % 2 == 0 then
            local s = tournament_details_mtt_frame_list_horizontal.transform.sizeDelta
            s.x = width
            tournament_details_mtt_frame_list_horizontal.transform.sizeDelta = s
        end

        if r[1][1] == r[1][2] then
            bee.setText(self:find("TextRank", item), _F("#{p1}", r[1][1]))
        else
            bee.setText(self:find("TextRank", item), _F("#{p1}-#{p2}", r[1][1], r[1][2]))
        end

        local TextNum = self:find("TextNum", item)
        for k, v in ipairs(r) do
            local item = TextNum
            if k > 1 then
                item = CU.GameObject.Instantiate(TextNum, item.transform.parent, false)
                item:SetActive(true)
                item.transform.localPosition = bee.v3(self.TitlePoses[k].x, 0)
            end
            bee.setText(item, v[3] / 100)
        end
    end
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

return P