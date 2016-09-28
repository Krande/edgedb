##
# Copyright (c) 2012-2016 MagicStack Inc.
# All rights reserved.
#
# See LICENSE for details.
##


import os.path
import unittest

from edgedb.server import _testbase as tb
from edgedb.client import exceptions as exc


class TestEdgeQLSelect(tb.QueryTestCase):
    SCHEMA = os.path.join(os.path.dirname(__file__), 'schemas',
                          'queries.eschema')

    SETUP = """
        WITH MODULE test
        INSERT Priority {
            name := 'High'
        };

        WITH MODULE test
        INSERT Priority {
            name := 'Low'
        };

        WITH MODULE test
        INSERT Status {
            name := 'Open'
        };

        WITH MODULE test
        INSERT Status {
            name := 'Closed'
        };


        WITH MODULE test
        INSERT User {
            name := 'Elvis'
        };

        WITH MODULE test
        INSERT User {
            name := 'Yury'
        };


        WITH MODULE test
        INSERT LogEntry {
            owner := (SELECT User WHERE User.name = 'Elvis'),
            spent_time := 50000,
            body := 'Rewriting everything.'
        };

        WITH MODULE test
        INSERT Issue {
            number := '1',
            name := 'Release EdgeDB',
            body := 'Initial public release of EdgeDB.',
            owner := (SELECT User WHERE User.name = 'Elvis'),
            watchers := (SELECT User WHERE User.name = 'Yury'),
            status := (SELECT Status WHERE Status.name = 'Open'),
            time_spent_log := (SELECT LogEntry),
            time_estimate := 3000
        };

        WITH MODULE test
        INSERT Comment {
            body := 'EdgeDB needs to happen soon.',
            owner := (SELECT User WHERE User.name = 'Elvis'),
            issue := (SELECT Issue WHERE Issue.number = '1')
        };


        WITH MODULE test
        INSERT Issue {
            number := '2',
            name := 'Improve EdgeDB repl output rendering.',
            body := 'We need to be able to render data in tabular format.',
            owner := (SELECT User WHERE User.name = 'Yury'),
            watchers := (SELECT User WHERE User.name = 'Elvis'),
            status := (SELECT Status WHERE Status.name = 'Open'),
            priority := (SELECT Priority WHERE Priority.name = 'High')
        };

        WITH MODULE test
        INSERT Issue {
            number := '3',
            name := 'Repl tweak.',
            body := 'Minor lexer tweaks.',
            owner := (SELECT User WHERE User.name = 'Yury'),
            watchers := (SELECT User WHERE User.name = 'Elvis'),
            status := (SELECT Status WHERE Status.name = 'Closed'),
            related_to := (SELECT Issue WHERE Issue.number = '2'),
            priority := (SELECT Priority WHERE Priority.name = 'Low')
        };

        WITH MODULE test
        INSERT Issue {
            number := '4',
            name := 'Regression.',
            body := 'Fix regression introduced by lexer tweak.',
            owner := (SELECT User WHERE User.name = 'Elvis'),
            status := (SELECT Status WHERE Status.name = 'Closed'),
            related_to := (SELECT Issue WHERE Issue.number = '3')
        };
    """

    async def test_edgeql_select_computable01(self):
        await self.assert_query_result('''
            WITH MODULE test
            SELECT
                Issue {
                    number,
                    aliased_number := Issue.number,
                    total_time_spent := (
                        SELECT sum(Issue.time_spent_log.spent_time)
                    )
                }
            WHERE
                Issue.number = '1';
        ''', [
            [{
                'number': '1',
                'aliased_number': '1',
                'total_time_spent': 50000
            }]
        ])

    async def test_edgeql_select_computable02(self):
        await self.assert_query_result('''
            WITH MODULE test
            SELECT
                Issue {
                    number,
                    total_time_spent := (
                        SELECT sum(Issue.time_spent_log.spent_time)
                    )
                }
            WHERE
                Issue.number = '1';
        ''', [
            [{
                'number': '1',
                'total_time_spent': 50000
            }]
        ])

    async def test_edgeql_select_computable03(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                User {
                    name,
                    shortest_own_text := (
                        SELECT Text {body}
                        WHERE Text.owner = User
                        ORDER BY strlen(Text.body) ASC
                        LIMIT 1
                    ),
                }
            WHERE User.name = 'Elvis';
        ''', [
            [{
                'name': 'Elvis',
                'shortest_own_text': {
                    'body': 'Rewriting everything.',
                },
            }]
        ])

    async def test_edgeql_select_computable04(self):
        await self.assert_query_result(r'''
            WITH
                MODULE test,
                # we aren't referencing User in any way, so this works
                # best as a subquery, rather than inline computable
                sub := (
                    SELECT Text {body}
                    ORDER BY strlen(Text.body) ASC
                    LIMIT 1
                )
            SELECT
                User {
                    name,
                    shortest_text := sub,
                }
            WHERE User.name = 'Elvis';
        ''', [
            [{
                'name': 'Elvis',
                'shortest_text': {
                    'body': 'Minor lexer tweaks.',
                },
            }]
        ])

    async def test_edgeql_select_computable05(self):
        await self.assert_query_result(r'''
            WITH
                MODULE test,
                # we aren't referencing User in any way, so this works
                # best as a subquery, than inline computable
                sub := (
                    SELECT Text {body}
                    ORDER BY strlen(Text.body) ASC
                    LIMIT 1
                )
            SELECT
                User {
                    name,
                    shortest_own_text := (
                        SELECT Text {body}
                        WHERE Text.owner = User
                        ORDER BY strlen(Text.body) ASC
                        LIMIT 1
                    ),
                    shortest_text := sub,
                }
            WHERE User.name = 'Elvis';
        ''', [
            [{
                'name': 'Elvis',
                'shortest_own_text': {
                    'body': 'Rewriting everything.',
                },
                'shortest_text': {
                    'body': 'Minor lexer tweaks.',
                },
            }]
        ])

    async def test_edgeql_select_computable06(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                User {
                    name,
                    shortest_text := (
                        SELECT Text {body}
                        # a clause that references User and is always true
                        WHERE User IS User
                        ORDER BY strlen(Text.body) ASC
                        LIMIT 1
                    ),
                }
            WHERE User.name = 'Elvis';
        ''', [
            [{
                'name': 'Elvis',
                'shortest_text': {
                    'body': 'Minor lexer tweaks.',
                },
            }]
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_computable07(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                User {
                    name,
                    # ad-hoc computable with many results
                    special_texts := (
                        SELECT Text {body}
                        WHERE Text.owner != User
                        ORDER BY strlen(Text.body) DESC
                    ),
                }
            WHERE User.name = 'Elvis';
        ''', [
            [{
                'name': 'Elvis',
                'special_texts': [
                    {'body': 'We need to be able to render data in tabular format.'},
                    {'body': 'Fix regression introduced by lexer tweak.'},
                    {'body': 'Initial public release of EdgeDB.'},
                    {'body': 'EdgeDB needs to happen soon.'},
                    {'body': 'Rewriting everything.'},
                    {'body': 'Minor lexer tweaks.'}
                ],
            }]
        ])

    async def test_edgeql_select_computable08(self):
        await self.assert_query_result(r"""
            # get a user + the latest issue (regardless of owner), which has
            # the same number of characters in the status as the user's name
            WITH MODULE test
            SELECT User{
                name,
                special_issues := (
                    SELECT Issue{
                        name,
                        number,
                        owner: {
                            name
                        },
                        status: {
                            name
                        }
                    }
                    WHERE strlen(Issue.status.name) = strlen(User.name)
                    ORDER BY Issue.number DESC
                    LIMIT 1
                )
            }
            ORDER BY User.name;
            """, [
            [
                {
                    'name': 'Elvis',
                    'special_issues': None
                }, {
                    'name': 'Yury',
                    'special_issues': {
                        'name': 'Improve EdgeDB repl output rendering.',
                        'owner': {'name': 'Yury'},
                        'status': {'name': 'Open'},
                        'number': '2'
                    },
                }
            ],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_computable09(self):
        await self.assert_query_result(r"""
            # XXX: need a specialized ad-hoc computable
            WITH MODULE test
            SELECT Text{
                body,
                Issue.name,
                LogEntry.name := 'log',
                Comment.name := 'comment',
            }
            ORDER BY Text.body;
            """, [
            [
                {'body': 'EdgeDB needs to happen soon.',
                 'name': 'comment'},
                {'body': 'Fix regression introduced by lexer tweak.',
                 'name': 'Regression.'},
                {'body': 'Initial public release of EdgeDB.',
                 'name': 'Release EdgeDB'},
                {'body': 'Minor lexer tweaks.',
                 'name': 'Repl tweak.'},
                {'body': 'Rewriting everything.',
                 'name': 'log'},
                {'body': 'We need to be able to render data in tabular format.',
                 'name': 'Improve EdgeDB repl output rendering.'}
            ],
        ])

    async def test_edgeql_select_match01(self):
        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name LIKE '%edgedb'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name LIKE '%EdgeDB'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name LIKE '%Edge%'
            ORDER BY Issue.number;
        ''')

        self.assert_data_shape(res, [
            [],
            [{'number': '1'}],
            [{'number': '1'}, {'number': '2'}],
        ])

    async def test_edgeql_select_match02(self):
        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name NOT LIKE '%edgedb'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name NOT LIKE '%EdgeDB'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name NOT LIKE '%Edge%'
            ORDER BY Issue.number;
        ''')

        self.assert_data_shape(res, [
            [{'number': '1'}, {'number': '2'}, {'number': '3'},
             {'number': '4'}],
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
            [{'number': '3'}, {'number': '4'}],
        ])

    async def test_edgeql_select_match03(self):
        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name ILIKE '%edgedb'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name ILIKE '%EdgeDB'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name ILIKE '%re%'
            ORDER BY Issue.number;
        ''')

        self.assert_data_shape(res, [
            [{'number': '1'}],
            [{'number': '1'}],
            [{'number': '1'}, {'number': '2'}, {'number': '3'},
             {'number': '4'}],
        ])

    async def test_edgeql_select_match04(self):
        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name NOT ILIKE '%edgedb'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name NOT ILIKE '%EdgeDB'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name NOT ILIKE '%re%'
            ORDER BY Issue.number;
        ''')

        self.assert_data_shape(res, [
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
            [],
        ])

    async def test_edgeql_select_match05(self):
        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name @@ 'edgedb'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.body @@ 'need'
            ORDER BY Issue.number;
        ''')

        self.assert_data_shape(res, [
            [{'number': '1'}, {'number': '2'}],
            [{'number': '2'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_match06(self):
        res = await self.con.execute(r'''
            # XXX: @@ used with a query operand, as opposed to a literal
            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name @@ to_tsquery('edgedb & repl')
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT
                Issue {number}
            WHERE
                Issue.name @@ to_tsquery('edgedb | repl')
            ORDER BY Issue.number;
        ''')

        self.assert_data_shape(res, [
            [{'number': '1'}, {'number': '2'}, {'number': '3'}],
            [{'number': '2'}],
        ])

    async def test_edgeql_select_match07(self):
        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT
                Text {body}
            WHERE
                Text.body ~ 'ed'
            ORDER BY Text.body;

            WITH MODULE test
            SELECT
                Text {body}
            WHERE
                Text.body ~ 'eD'
            ORDER BY Text.body;

            WITH MODULE test
            SELECT
                Text {body}
            WHERE
                Text.body ~ 'ed([S\s]|$)'
            ORDER BY Text.body;
        ''')

        self.assert_data_shape(res, [
            [{'body': 'EdgeDB needs to happen soon.'},
             {'body': 'Fix regression introduced by lexer tweak.'},
             {'body': 'We need to be able to render data in tabular format.'}],
            [{'body': 'EdgeDB needs to happen soon.'},
             {'body': 'Initial public release of EdgeDB.'}],
            [{'body': 'Fix regression introduced by lexer tweak.'},
             {'body': 'We need to be able to render data in tabular format.'}]
        ])

    async def test_edgeql_select_match08(self):
        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT
                Text {body}
            WHERE
                Text.body ~* 'ed'
            ORDER BY Text.body;

            WITH MODULE test
            SELECT
                Text {body}
            WHERE
                Text.body ~* 'eD'
            ORDER BY Text.body;

            WITH MODULE test
            SELECT
                Text {body}
            WHERE
                Text.body ~* 'ed([S\s]|$)'
            ORDER BY Text.body;
        ''')

        self.assert_data_shape(res, [
            [{'body': 'EdgeDB needs to happen soon.'},
             {'body': 'Fix regression introduced by lexer tweak.'},
             {'body': 'Initial public release of EdgeDB.'},
             {'body': 'We need to be able to render data in tabular format.'}],
            [{'body': 'EdgeDB needs to happen soon.'},
             {'body': 'Fix regression introduced by lexer tweak.'},
             {'body': 'Initial public release of EdgeDB.'},
             {'body': 'We need to be able to render data in tabular format.'}],
            [{'body': 'EdgeDB needs to happen soon.'},
             {'body': 'Fix regression introduced by lexer tweak.'},
             {'body': 'We need to be able to render data in tabular format.'}],
        ])

    async def test_edgeql_select_type01(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                Issue {
                    number,
                    __type__: {
                        name
                    }
                }
            WHERE
                Issue.number = '1';
        ''', [
            [{
                'number': '1',
                '__type__': {'name': 'test::Issue'},
            }],
        ])

    async def test_edgeql_select_type02(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT User.__type__.name LIMIT 1;
        ''', [
            ['test::User']
        ])

    async def test_edgeql_select_recursive01(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                Issue {
                    number,
                    <related_to: {
                        number,
                    },
                }
            WHERE
                Issue.number = '2';

            WITH MODULE test
            SELECT
                Issue {
                    number,
                    <related_to *1
                }
            WHERE
                Issue.number = '2';
        ''', [
            [{
                'number': '2',
                'related_to': [{
                    'number': '3',
                }]
            }],
            [{
                'number': '2',
                'related_to': [{
                    'number': '3',
                }]
            }],
        ])

    async def test_edgeql_select_limit01(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                Issue {number}
            ORDER BY Issue.number
            OFFSET 2;

            WITH MODULE test
            SELECT
                Issue {number}
            ORDER BY Issue.number
            LIMIT 3;

            WITH MODULE test
            SELECT
                Issue {number}
            ORDER BY Issue.number
            OFFSET 2 LIMIT 3;
        ''', [
            [{'number': '3'}, {'number': '4'}],
            [{'number': '1'}, {'number': '2'}, {'number': '3'}],
            [{'number': '3'}, {'number': '4'}],
        ])

    async def test_edgeql_select_specialized01(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                Text {body}
            ORDER BY Text.body;

            WITH MODULE test
            SELECT
                Text {
                    Issue.name,
                    body,
                }
            ORDER BY Text.body;
        ''', [
            [
                {'body': 'EdgeDB needs to happen soon.'},
                {'body': 'Fix regression introduced by lexer tweak.'},
                {'body': 'Initial public release of EdgeDB.'},
                {'body': 'Minor lexer tweaks.'},
                {'body': 'Rewriting everything.'},
                {'body': 'We need to be able to render data in tabular format.'}
            ],
            [
                {'body': 'EdgeDB needs to happen soon.',
                 'name': None},
                {'body': 'Fix regression introduced by lexer tweak.',
                 'name': 'Regression.'},
                {'body': 'Initial public release of EdgeDB.',
                 'name': 'Release EdgeDB'},
                {'body': 'Minor lexer tweaks.',
                 'name': 'Repl tweak.'},
                {'body': 'Rewriting everything.',
                 'name': None},
                {'body': 'We need to be able to render data in tabular format.',
                 'name': 'Improve EdgeDB repl output rendering.'}
            ]
        ])

    async def test_edgeql_select_specialized02(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT User{
                name,
                <owner: LogEntry {
                    body
                },
            } WHERE User.name = 'Elvis';
        ''', [
            [{
                'name': 'Elvis',
                'owner': [
                    {'body': 'Rewriting everything.'}
                ],
            }],
        ])

    async def test_edgeql_select_specialized03(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT User{
                name,
                <owner: Issue {
                    number
                } WHERE <int>(User.<owner[TO Issue].number) < 3,
            } WHERE User.name = 'Elvis';
        ''', [
            [{
                'name': 'Elvis',
                'owner': [
                    {'number': '1'},
                ],
            }],
        ])

    async def test_edgeql_select_shape01(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{
                number,
                related_to: {
                    number
                } WHERE Issue.related_to.owner = Issue.owner,
            } ORDER BY Issue.number;
        ''', [
            [{
                'number': '1',
                'related_to': []
            }, {
                'number': '2',
                'related_to': []
            }, {
                'number': '3',
                'related_to': [
                    {'number': '2'}
                ]
            }, {
                'number': '4',
                'related_to': []
            }],
        ])

    async def test_edgeql_select_shape02(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT User{
                name,
                <owner: Issue {
                    number
                } WHERE EXISTS User.<owner[TO Issue].related_to,
            } ORDER BY User.name;
        ''', [
            [{
                'name': 'Elvis',
                'owner': [{
                    'number': '4'
                }]
            }, {
                'name': 'Yury',
                'owner': [{
                    'number': '3'
                }]
            }],
        ])

    async def test_edgeql_select_shape03(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT User{
                name,
                <owner: Issue {
                    number
                } ORDER BY User.<owner[TO Issue].number DESC,
            } ORDER BY User.name;
        ''', [
            [{
                'name': 'Elvis',
                'owner': [{
                    'number': '4'
                }, {
                    'number': '1'
                }]
            }, {
                'name': 'Yury',
                'owner': [{
                    'number': '3'
                }, {
                    'number': '2'
                }]
            }],
        ])

    async def test_edgeql_select_instance01(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                Text {body}
            WHERE Text IS Comment
            ORDER BY Text.body;
        ''', [
            [
                {'body': 'EdgeDB needs to happen soon.'},
            ],
        ])

    async def test_edgeql_select_instance02(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                Text {body}
            WHERE Text IS NOT (Comment, Issue)
            ORDER BY Text.body;
        ''', [
            [
                {'body': 'Rewriting everything.'},
            ],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_instance03(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                Text {body}
            WHERE Text IS Issue AND (Text AS Issue).number = 1
            ORDER BY Text.body;
        ''', [
            [
                {'body': 'Initial public release of EdgeDB.'},
            ],
        ])

    async def test_edgeql_select_combined01(self):
        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT
                Issue {name, body}
            UNION
            SELECT
                Comment {body};

            WITH MODULE test
            SELECT
                Text {body}
            INTERSECT
            SELECT
                Comment {body};

            WITH MODULE test
            SELECT
                Text {body}
            EXCEPT
            SELECT
                Comment {body};
        ''')
        # sorting manually to test basic functionality first
        for r in res:
            r.sort(key=lambda x: x['body'])

        self.assert_data_shape(res, [
            [
                {'body': 'EdgeDB needs to happen soon.'},
                {'body': 'Fix regression introduced by lexer tweak.',
                 'name': 'Regression.'},
                {'body': 'Initial public release of EdgeDB.',
                 'name': 'Release EdgeDB'},
                {'body': 'Minor lexer tweaks.',
                 'name': 'Repl tweak.'},
                {'body': 'We need to be able to render data in tabular format.',
                 'name': 'Improve EdgeDB repl output rendering.'}
            ],
            [
                {'body': 'EdgeDB needs to happen soon.'},
            ],
            [
                {'body': 'Fix regression introduced by lexer tweak.'},
                {'body': 'Initial public release of EdgeDB.'},
                {'body': 'Minor lexer tweaks.'},
                {'body': 'Rewriting everything.'},
                {'body': 'We need to be able to render data in tabular format.'}
            ],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_combined02(self):
        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT
                Issue {name, body}
            UNION
            SELECT
                Comment {body}
            ORDER BY (Object AS Text).body;

            WITH MODULE test
            SELECT
                Text {body}
            INTERSECT
            SELECT
                Comment {body}
            ORDER BY (Object AS Text).body;

            WITH MODULE test
            SELECT
                Text {body}
            EXCEPT
            SELECT
                Comment {body}
            ORDER BY (Object AS Text).body;
        ''')

        self.assert_data_shape(res, [
            [
                {'body': 'EdgeDB needs to happen soon.'},
                {'body': 'Fix regression introduced by lexer tweak.',
                 'name': 'Regression.'},
                {'body': 'Initial public release of EdgeDB.',
                 'name': 'Release EdgeDB'},
                {'body': 'Minor lexer tweaks.',
                 'name': 'Repl tweak.'},
                {'body': 'We need to be able to render data in tabular format.',
                 'name': 'Improve EdgeDB repl output rendering.'}
            ],
            [
                {'body': 'EdgeDB needs to happen soon.'},
            ],
            [
                {'body': 'Fix regression introduced by lexer tweak.'},
                {'body': 'Initial public release of EdgeDB.'},
                {'body': 'Minor lexer tweaks.'},
                {'body': 'Rewriting everything.'},
                {'body': 'We need to be able to render data in tabular format.'}
            ],
        ])

    async def test_edgeql_select_order01(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue {name}
            ORDER BY Issue.priority.name ASC NULLS LAST THEN Issue.name;

            WITH MODULE test
            SELECT Issue {name}
            ORDER BY Issue.priority.name ASC NULLS FIRST THEN Issue.name;
        ''', [
            [
                {'name': 'Improve EdgeDB repl output rendering.'},
                {'name': 'Repl tweak.'},
                {'name': 'Regression.'},
                {'name': 'Release EdgeDB'},
            ],
            [
                {'name': 'Regression.'},
                {'name': 'Release EdgeDB'},
                {'name': 'Improve EdgeDB repl output rendering.'},
                {'name': 'Repl tweak.'},
            ]
        ])

    async def test_edgeql_select_order02(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Text {body}
            ORDER BY strlen(Text.body) DESC;
        ''', [[
            {'body': 'We need to be able to render data in tabular format.'},
            {'body': 'Fix regression introduced by lexer tweak.'},
            {'body': 'Initial public release of EdgeDB.'},
            {'body': 'EdgeDB needs to happen soon.'},
            {'body': 'Rewriting everything.'},
            {'body': 'Minor lexer tweaks.'}
        ]])

    async def test_edgeql_select_order03(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT User {name}
            ORDER BY (
                SELECT sum(<int>User.<watchers.number)
            );
        ''', [
            [
                {'name': 'Yury'},
                {'name': 'Elvis'},
            ]
        ])

    async def test_edgeql_select_where01(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            # issue where the owner also has a comment with non-empty body
            WHERE Issue.owner.<owner[TO Comment].body != '';
        ''', [
            [{'number': '1'}, {'number': '4'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_where02(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            # issue where the owner also has a comment to it
            WHERE Issue.owner.<owner[TO Comment].issue = Issue;
        ''', [
            [{'number': '1'}],
        ])

    async def test_edgeql_select_where03(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{
                name,
                number,
                owner: {
                    name
                },
                status: {
                    name
                }
            } WHERE strlen(Issue.status.name) = 4;
            ''', [
            [{
                'owner': {'name': 'Elvis'},
                'status': {'name': 'Open'},
                'name': 'Release EdgeDB',
                'number': '1'
            }, {
                'owner': {'name': 'Yury'},
                'status': {'name': 'Open'},
                'name': 'Improve EdgeDB repl output rendering.',
                'number': '2'
            }],
        ])

    async def test_edgeql_select_func01(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT std::strlen(User.name) ORDER BY User.name;

            WITH MODULE test
            SELECT std::sum(<std::int>Issue.number);
        ''', [
            [5, 4],
            [10]
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_func02(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT std::lower(string:=User.name) ORDER BY User.name;
        ''', [
            ['elvis', 'yury'],
        ])

    async def test_edgeql_select_func03(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT std::count(User.<owner.id)
            GROUP BY User.name ORDER BY User.name;
        ''', [
            [4, 2],
        ])

    async def test_edgeql_select_func04(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT sum(<int>Issue.number)
            WHERE EXISTS Issue.watchers.name
            GROUP BY Issue.watchers.name
            ORDER BY Issue.watchers.name;
        ''', [
            [5, 1],
        ])

    async def test_edgeql_select_exists01(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                Issue {
                    number
                }
            WHERE
                NOT EXISTS Issue.time_estimate;

            WITH MODULE test
            SELECT
                Issue {
                    number
                }
            WHERE
                EXISTS Issue.time_estimate;
        ''', [
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
            [{'number': '1'}],
        ])

    async def test_edgeql_select_exists02(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                Issue {
                    number
                }
            WHERE
                NOT EXISTS (Issue.<issue[TO Comment]);
        ''', [
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
        ])

    async def test_edgeql_select_exists03(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                Issue {
                    number
                }
            WHERE
                NOT EXISTS (SELECT Issue.<issue[TO Comment]);
        ''', [
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
        ])

    async def test_edgeql_select_exists04(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT
                Issue {
                    number
                }
            WHERE
                EXISTS (Issue.<issue[TO Comment]);
        ''', [
            [{'number': '1'}],
        ])

    async def test_edgeql_select_exists05(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.priority           # has Priority [2, 3]
            ORDER BY Issue.number;
        ''', [
            [{'number': '2'}, {'number': '3'}],
        ])

    async def test_edgeql_select_exists06(self):
        # using IDs in EXISTS clauses should be semantically identical
        # to using concepts
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.priority.id        # has Priority [2, 3]
            ORDER BY Issue.number;
        ''', [
            [{'number': '2'}, {'number': '3'}],
        ])

    async def test_edgeql_select_exists07(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.<issue             # has Comment [1]
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_exists08(self):
        # using IDs in EXISTS clauses should be semantically identical
        # to using concepts
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.<issue.id          # has Comment [1]
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}],
        ])

    async def test_edgeql_select_exists09(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority       # has no Priority [1, 4]
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}, {'number': '4'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_exists10(self):
        # using IDs in EXISTS clauses should be semantically identical
        # to using concepts
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority.id    # has no Priority [1, 4]
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}, {'number': '4'}],
        ])

    async def test_edgeql_select_exists11(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.<issue         # has no Comment [2, 3, 4]
            ORDER BY Issue.number;
        ''', [
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_exists12(self):
        # using IDs in EXISTS clauses should be semantically identical
        # to using concepts
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.<issue.id      # has no Comment [2, 3, 4]
            ORDER BY Issue.number;
        ''', [
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
        ])

    async def test_edgeql_select_exists13(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            # issue where the owner also has a comment
            WHERE EXISTS Issue.owner.<owner[TO Comment];
        ''', [
            [{'number': '1'}, {'number': '4'}],
        ])

    async def test_edgeql_select_exists14(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            # issue where the owner also has a comment to it
            WHERE
                EXISTS (
                    SELECT Comment
                    WHERE
                        Comment.owner = Issue.owner
                        AND
                        Comment.issue = Issue
                );
        ''', [
            [{'number': '1'}],
        ])

    async def test_edgeql_select_exists15(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            # issue where the owner also has a comment, but not to the
            # issue itself
            WHERE
                EXISTS (
                    SELECT Comment
                    WHERE
                        Comment.owner = Issue.owner
                        AND
                        Comment.issue != Issue
                );
        ''', [
            [{'number': '4'}],
        ])

    async def test_edgeql_select_exists16(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            # issue where the owner also has a comment, but not to the
            # issue itself
            WHERE
                EXISTS (
                    SELECT Comment
                    WHERE
                        Comment.owner = Issue.owner
                        AND
                        Comment.issue.id != Issue.id
                );
        ''', [
            [{'number': '4'}],
        ])

    async def test_edgeql_select_exists17(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            # issue where the owner also has a comment, but not to the
            # issue itself
            WHERE
                EXISTS (
                    SELECT Comment
                    WHERE
                        Comment.owner = Issue.owner
                        AND
                        NOT Comment.issue = Issue
                );
        ''', [
            [{'number': '4'}],
        ])

    async def test_edgeql_select_and01(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.priority           # has Priority [2, 3]
                AND
                EXISTS Issue.<issue             # has Comment [1]
            ORDER BY Issue.number;
        ''', [
            [],
        ])

    async def test_edgeql_select_and02(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.priority.id        # has Priority [2, 3]
                AND
                EXISTS Issue.<issue             # has Comment [1]
            ORDER BY Issue.number;
        ''', [
            [],
        ])

    async def test_edgeql_select_and03(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority       # has no Priority [1, 4]
                AND
                NOT EXISTS Issue.<issue         # has no Comment [2, 3, 4]
            ORDER BY Issue.number;
        ''', [
            [{'number': '4'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_and04(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority.id    # has no Priority [1, 4]
                AND
                NOT EXISTS Issue.<issue         # has no Comment [2, 3, 4]
            ORDER BY Issue.number;
        ''', [
            [{'number': '4'}],
        ])

    async def test_edgeql_select_and05(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority       # has no Priority [1, 4]
                AND
                EXISTS Issue.<issue             # has Comment [1]
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_and06(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority       # has no Priority [1, 4]
                AND
                EXISTS Issue.<issue.id          # has Comment [1]
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}],
        ])

    async def test_edgeql_select_and07(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.priority           # has Priority [2, 3]
                AND
                NOT EXISTS Issue.<issue         # has no Comment [2, 3, 4]
            ORDER BY Issue.number;
        ''', [
            [{'number': '2'}, {'number': '3'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_and08(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.priority           # has Priority [2, 3]
                AND
                NOT EXISTS Issue.<issue.id      # has no Comment [2, 3, 4]
            ORDER BY Issue.number;
        ''', [
            [{'number': '2'}, {'number': '3'}],
        ])

    async def test_edgeql_select_or01(self):
        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                Issue.priority.name = 'High'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT Issue{number}
            WHERE
                Issue.priority.name = 'Low'
            ORDER BY Issue.number;
        ''')

        issues_h, issues_l = res

        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                Issue.priority.name = 'High'
                OR
                Issue.priority.name = 'Low'
            ORDER BY Issue.priority.name THEN Issue.number;
        ''')

        self.assert_data_shape(res, [
            issues_h + issues_l,
        ])

    async def test_edgeql_select_or02(self):
        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                Issue.priority.name = 'High'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority
            ORDER BY Issue.number;
        ''')

        issues_h, issues_n = res

        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                Issue.priority.name = 'High'
                OR
                NOT EXISTS Issue.priority.name
            ORDER BY Issue.priority.name NULLS LAST THEN Issue.number;

            WITH MODULE test
            SELECT Issue{number}
            WHERE
                Issue.priority.name = 'High'
                OR
                NOT EXISTS Issue.priority.id
            ORDER BY Issue.priority.name NULLS LAST THEN Issue.number;
        ''')

        self.assert_data_shape(res, [
            issues_h + issues_n,
            issues_h + issues_n,
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_or03(self):
        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                Issue.priority.name = 'High'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority
            ORDER BY Issue.number;
        ''')

        issues_h, issues_n = res

        res = await self.con.execute(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                Issue.priority.name = 'High'
                OR
                NOT EXISTS Issue.priority
            ORDER BY Issue.priority.name NULLS LAST THEN Issue.number;
        ''')

        self.assert_data_shape(res, [
            issues_h + issues_n,
        ])

    async def test_edgeql_select_or04(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                Issue.priority.name = 'High'
                OR
                Issue.status.name = 'Closed'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT Issue{number}
            WHERE
                Issue.priority.name = 'High'
                OR
                Issue.priority.name = 'Low'
                OR
                Issue.status.name = 'Closed'
            ORDER BY Issue.number;

            WITH MODULE test
            SELECT Issue{number}
            WHERE
                Issue.priority.name IN ('High', 'Low')
                OR
                Issue.status.name = 'Closed'
            ORDER BY Issue.number;
        ''', [
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
            # it so happens that all low priority issues are also closed
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_or05(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority.id
                OR
                Issue.status.name = 'Closed'
            ORDER BY Issue.number;

            # should be identical
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority
                OR
                Issue.status.name = 'Closed'
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}, {'number': '3'}, {'number': '4'}],
            [{'number': '1'}, {'number': '3'}, {'number': '4'}],
        ])

    async def test_edgeql_select_or06(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.priority           # has Priority [2, 3]
                OR
                EXISTS Issue.<issue             # has Comment [1]
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}, {'number': '2'}, {'number': '3'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_or07(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.priority.id        # has Priority [2, 3]
                OR
                EXISTS Issue.<issue             # has Comment [1]
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}, {'number': '2'}, {'number': '3'}],
        ])

    async def test_edgeql_select_or08(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority       # has no Priority [1, 4]
                OR
                NOT EXISTS Issue.<issue         # has no Comment [2, 3, 4]
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}, {'number': '2'}, {'number': '3'},
             {'number': '4'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_or09(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority.id    # has no Priority [1, 4]
                OR
                NOT EXISTS Issue.<issue         # has no Comment [2, 3, 4]
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}, {'number': '2'}, {'number': '3'},
             {'number': '4'}],
        ])

    async def test_edgeql_select_or10(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority       # has no Priority [1, 4]
                OR
                EXISTS Issue.<issue             # has Comment [1]
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}, {'number': '4'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_or11(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                NOT EXISTS Issue.priority       # has no Priority [1, 4]
                OR
                EXISTS Issue.<issue.id          # has Comment [1]
            ORDER BY Issue.number;
        ''', [
            [{'number': '1'}, {'number': '4'}],
        ])

    async def test_edgeql_select_or12(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.priority           # has Priority [2, 3]
                OR
                NOT EXISTS Issue.<issue         # has no Comment [2, 3, 4]
            ORDER BY Issue.number;
        ''', [
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_or13(self):
        await self.assert_query_result(r'''
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.priority           # has Priority [2, 3]
                OR
                NOT EXISTS Issue.<issue.id      # has no Comment [2, 3, 4]
            ORDER BY Issue.number;
        ''', [
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
        ])

    async def test_edgeql_select_null01(self):
        await self.assert_query_result(r"""
            SELECT test::Issue.number = NULL;
            """, [
            [None, None, None, None],
        ])

    async def test_edgeql_select_null02(self):
        await self.assert_query_result(r"""
            # the WHERE clause is always NULL, so it can never be true
            WITH MODULE test
            SELECT Issue{number}
            WHERE Issue.number = NULL;

            WITH MODULE test
            SELECT Issue{number}
            WHERE Issue.priority = NULL;

            WITH MODULE test
            SELECT Issue{number}
            WHERE Issue.priority.name = NULL;
            """, [
            [],
            [],
            [],
        ])

    async def test_edgeql_select_subqueries01(self):
        await self.assert_query_result(r"""
            WITH
                MODULE test,
                Issue2:= Issue
            # this is string concatenation, not integer arithmetic
            SELECT Issue.number + Issue2.number;
            """, [
            ['{}{}'.format(a, b) for a in range(1, 5) for b in range(1, 5)],
        ])

    async def test_edgeql_select_subqueries02(self):
        await self.assert_query_result(r"""
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                Issue.number IN ('2', '3', '4')
                AND
                EXISTS (
                    # due to common prefix, the Issue referred to here is
                    # the same Issue as in the LHS of AND, therefore
                    # this condition can never be true
                    SELECT Issue WHERE Issue.number IN ('1', '6')
                );
            """, [
            [],
        ])

    async def test_edgeql_select_subqueries03(self):
        await self.assert_query_result(r"""
            WITH
                MODULE test,
                # subqueries aliased here are independent of the main query,
                # therefore Issue in this subquery is different from the
                # main query
                sub:= (SELECT Issue WHERE Issue.number IN ('1', '6'))
            SELECT Issue{number}
            WHERE
                Issue.number IN ('2', '3', '4')
                AND
                EXISTS sub;
            """, [
            [{'number': '2'}, {'number': '3'}, {'number': '4'}],
        ])

    async def test_edgeql_select_subqueries04(self):
        # XXX: aliases vs. independent queries need to be fixed
        await self.assert_query_result(r"""
            # find all issues such that there's at least one more
            # issue with the same priority
            WITH
                MODULE test,
                Issue2:= Issue
            SELECT Issue{number}
            WHERE
                Issue != Issue2
                AND
                # NOTE: this condition is false when one of the sides is NULL
                Issue.priority = Issue2.priority;
            """, [
            [],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_subqueries05(self):
        # XXX: aliases vs. independent queries need to be fixed
        await self.assert_query_result(r"""
            # find all issues such that there's at least one more
            # issue with the same priority (even if the "same" means NULL)
            WITH
                MODULE test,
                Issue2:= Issue
            SELECT Issue{number}
            WHERE
                Issue != Issue2
                AND
                (
                    Issue.priority = Issue2.priority
                    OR

                    NOT EXISTS Issue.priority.id
                    AND
                    NOT EXISTS Issue2.priority.id
                );
            """, [
            [{'number': '1'}, {'number': '4'}],
        ])

    async def test_edgeql_select_subqueries06(self):
        await self.assert_query_result(r"""
            # find all issues such that there's at least one more
            # issue watched by the same user as this one
            WITH MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.watchers
                AND
                EXISTS (
                    SELECT User.<watchers
                    WHERE
                        User = Issue.watchers
                        AND
                        User.<watchers != Issue
                );
            """, [
            [{'number': '2'}, {'number': '3'}],
        ])

    @unittest.expectedFailure
    async def test_edgeql_select_subqueries07(self):
        await self.assert_query_result(r"""
            # find all issues such that there's at least one more
            # issue watched by the same user as this one
            WITH
                MODULE test
            SELECT Issue{number}
            WHERE
                EXISTS Issue.watchers
                AND
                EXISTS (
                    SELECT Text
                    WHERE
                        Text IS Issue
                        AND
                        (Text AS Issue).watchers = Issue.watchers
                        AND
                        Text != Issue
                );
            """, [
            [{'number': '2'}, {'number': '3'}],
        ])

    async def test_edgeql_select_subqueries08(self):
        # XXX: I'm not actually sure that this should work, much less
        # what the result should be
        await self.assert_query_result(r"""
            WITH MODULE test
            SELECT Issue.number + (SELECT Issue.number);
            """, [
            ['1"1"', '2"2"', '3"3"', '4"4"'],
        ])

    async def test_edgeql_select_subqueries09(self):
        with self.assertRaisesRegex(
                exc._base.UnknownEdgeDBError,
                r'unexpected binop operands'):
            await self.con.execute(r"""
                WITH
                    MODULE test,
                    sub:= (SELECT Issue.number)
                SELECT Issue.number + sub;
                """)

    async def test_edgeql_select_subqueries10(self):
        await self.assert_query_result(r"""
            WITH MODULE test
            SELECT Text{
                Issue.number,
                body_length:= strlen(Text.body)
            } ORDER BY strlen(Text.body);

            # find all issues such that there's at least one more
            # Text item of similar body length (+/-5 characters)
            WITH MODULE test
            SELECT Issue{
                number,
            }
            WHERE
                EXISTS (
                    SELECT Text
                    WHERE
                        Text != Issue
                        AND
                        (strlen(Text.body) - strlen(Issue.body)) ^ 2 <= 25
                )
            ORDER BY Issue.number;
            """, [
            [
                {'number': '3', 'body_length': 19},
                {'number': None, 'body_length': 21},
                {'number': None, 'body_length': 28},
                {'number': '1', 'body_length': 33},
                {'number': '4', 'body_length': 41},
                {'number': '2', 'body_length': 52},
            ],
            [{'number': '1'}, {'number': '3'}],
        ])

    async def test_edgeql_select_subqueries11(self):
        await self.assert_query_result(r"""
            # same as above, but also include the body_length computable
            WITH MODULE test
            SELECT Issue{
                number,
                body_length:= strlen(Issue.body)
            }
            WHERE
                EXISTS (
                    SELECT Text
                    WHERE
                        Text != Issue
                        AND
                        (strlen(Text.body) - strlen(Issue.body)) ^ 2 <= 25
                )
            ORDER BY Issue.number;
            """, [
            [{
                'number': '1',
                'body_length': 33,
            }, {
                'number': '3',
                'body_length': 19,
            }],
        ])
