import React from 'react'
import { connect } from 'redux-bundler-react'

function TestTag (props) {
  const { testTag } = props
  return (
    <li className='dib ttsc mr2 mb2 ph2 pv1 mid-gray'>
      { testTag }
    </li>
  )
}

function TestTagsList (props) {
  const { testTagsIndex } = props

  if (testTagsIndex == null) return null
  if (testTagsIndex.length === 0) return null

  return (
    <div className="mt4 pl0">
      <p>Tests are coming from:</p>
      <div className="scrollbox">
      <ul className='list pl0 ml0'>
      {testTagsIndex.map(testTag => {
          return <TestTag testTag={ testTag } />
        })}
      </ul>
    </div>
    </div>
  )
}

export default connect(
  'selectTestTagsIndex',
  TestTagsList
)
